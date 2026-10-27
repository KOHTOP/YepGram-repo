import Foundation
import Postbox
import SwiftSignalKit
internal import TelegramApi
import SGSimpleSettings

private let yepGramDeveloperUserIds: Set<Int64> = [8859530230]

/// YepGram's developer badge is shown next to these users' names.
public func yepGramIsDeveloper(_ peerId: PeerId) -> Bool {
    return peerId.namespace == Namespaces.Peer.CloudUser && yepGramDeveloperUserIds.contains(peerId.id._internalGetInt64Value())
}

/// Ghost mode, "read after action": replying, reacting or voting in a chat sends its read mark,
/// which ghost mode otherwise keeps local.
func _internal_yepGramReadAfterAction(account: Account, peerId: PeerId) {
    let accountId = account.peerId.id._internalGetInt64Value()
    guard YepGramSettings.ghost(.noReadReceipts, accountId: accountId) && YepGramSettings.ghost(.readAfterAction, accountId: accountId) else {
        return
    }
    if peerId.namespace == Namespaces.Peer.SecretChat {
        return
    }
    let network = account.network
    let stateManager = account.stateManager
    let _ = (account.postbox.transaction { transaction -> (Peer?, Int32?) in
        var maxIncomingReadId: Int32?
        for (namespace, state) in transaction.getPeerReadStates(peerId) ?? [] {
            if namespace == Namespaces.Message.Cloud, case let .idBased(maxId, _, _, _, _) = state {
                maxIncomingReadId = maxId
            }
        }
        return (transaction.getPeer(peerId), maxIncomingReadId)
    }
    |> mapToSignal { peer, maxIncomingReadId -> Signal<Never, NoError> in
        guard let peer, let maxIncomingReadId, maxIncomingReadId > 0 else {
            return .complete()
        }
        if peer is TelegramChannel {
            guard let inputChannel = apiInputChannel(peer) else {
                return .complete()
            }
            return network.request(Api.functions.channels.readHistory(channel: inputChannel, maxId: maxIncomingReadId))
            |> `catch` { _ -> Signal<Api.Bool, NoError> in
                return .complete()
            }
            |> ignoreValues
        }
        guard let inputPeer = apiInputPeer(peer) else {
            return .complete()
        }
        return network.request(Api.functions.messages.readHistory(peer: inputPeer, maxId: maxIncomingReadId))
        |> map(Optional.init)
        |> `catch` { _ -> Signal<Api.messages.AffectedMessages?, NoError> in
            return .single(nil)
        }
        |> mapToSignal { result -> Signal<Never, NoError> in
            if let result, case let .affectedMessages(data) = result {
                stateManager.addUpdateGroups([.updatePts(pts: data.pts, ptsCount: data.ptsCount)])
            }
            return .complete()
        }
    }).start()
}
