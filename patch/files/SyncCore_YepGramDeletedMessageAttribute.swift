import Foundation
import Postbox
import SGSimpleSettings

// YepGram: a message the server deleted is kept locally and carries this attribute,
// so the chat can still show it with a "deleted" mark next to its time.
public final class YepGramDeletedMessageAttribute: MessageAttribute, Equatable {
    public let deletedAt: Int32

    public init(deletedAt: Int32) {
        self.deletedAt = deletedAt
    }

    public required init(decoder: PostboxDecoder) {
        self.deletedAt = decoder.decodeInt32ForKey("d", orElse: 0)
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeInt32(self.deletedAt, forKey: "d")
    }

    public static func ==(lhs: YepGramDeletedMessageAttribute, rhs: YepGramDeletedMessageAttribute) -> Bool {
        return lhs.deletedAt == rhs.deletedAt
    }
}

public extension Message {
    var yepGramIsDeleted: Bool {
        for attribute in self.attributes {
            if attribute is YepGramDeletedMessageAttribute {
                return true
            }
        }
        return false
    }
}

private func yepGramShouldKeepDeletedMessage(_ message: Message) -> Bool {
    if message.id.namespace != Namespaces.Message.Cloud {
        return false
    }
    for media in message.media {
        if media is TelegramMediaAction {
            return false
        }
    }
    return true
}

/// Marks the stored messages among `ids` as deleted instead of removing them.
/// Returns the ids that were not kept, which the caller deletes as before.
func _internal_yepGramKeepDeletedMessages(transaction: Transaction, ids: [MessageId]) -> [MessageId] {
    if !YepGramSettings.keepDeletedMessages {
        return ids
    }
    let timestamp = Int32(Date().timeIntervalSince1970)
    var notKept: [MessageId] = []
    for id in ids {
        guard let message = transaction.getMessage(id), yepGramShouldKeepDeletedMessage(message) else {
            notKept.append(id)
            continue
        }
        if message.yepGramIsDeleted {
            continue
        }
        transaction.updateMessage(id, update: { currentMessage in
            var storeForwardInfo: StoreMessageForwardInfo?
            if let forwardInfo = currentMessage.forwardInfo {
                storeForwardInfo = StoreMessageForwardInfo(authorId: forwardInfo.author?.id, sourceId: forwardInfo.source?.id, sourceMessageId: forwardInfo.sourceMessageId, date: forwardInfo.date, authorSignature: forwardInfo.authorSignature, psaType: forwardInfo.psaType, flags: forwardInfo.flags)
            }
            var attributes = currentMessage.attributes
            attributes.append(YepGramDeletedMessageAttribute(deletedAt: timestamp))
            return .update(StoreMessage(id: currentMessage.id, customStableId: nil, globallyUniqueId: currentMessage.globallyUniqueId, groupingKey: currentMessage.groupingKey, threadId: currentMessage.threadId, timestamp: currentMessage.timestamp, flags: StoreMessageFlags(currentMessage.flags), tags: currentMessage.tags, globalTags: currentMessage.globalTags, localTags: currentMessage.localTags, forwardInfo: storeForwardInfo, authorId: currentMessage.author?.id, text: currentMessage.text, attributes: attributes, media: currentMessage.media))
        })
    }
    return notKept
}
