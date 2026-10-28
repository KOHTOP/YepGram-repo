#!/usr/bin/env python3
"""Applies the YepGram changes to a Swiftgram/Telegram-iOS checkout.

Usage: python3 patch/apply.py <path to Telegram-iOS checkout>

Every edit looks for an exact anchor in the upstream source and fails loudly when
the anchor is missing, so an upstream change shows up as a clear error instead of a
silently half-patched build.
"""

import os
import re
import shutil
import sys

PATCH_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(PATCH_DIR, 'files')

failures = []


def read(root, path):
    with open(os.path.join(root, path), encoding='utf-8', newline='') as f:
        return f.read()


def write(root, path, text):
    with open(os.path.join(root, path), 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def replace(root, path, old, new, count=1):
    text = read(root, path)
    found = text.count(old)
    if found != count:
        failures.append('{}: expected {} match(es), found {}:\n{}'.format(path, count, found, old))
        return
    write(root, path, text.replace(old, new))
    print('patched', path)


def rename_app(root):
    path = 'Telegram/BUILD'
    text = read(root, path)
    pattern = re.compile(r'(<string>[^<]*?)Swiftgram([^<]*</string>)')
    text, n = pattern.subn(r'\1YepGram\2', text)
    if n == 0:
        failures.append('{}: no Info.plist strings mention Swiftgram'.format(path))
        return
    write(root, path, text)
    print('patched', path, '({} strings)'.format(n))

    ko = 'Telegram/Telegram-iOS/ko.lproj/InfoPlist.strings'
    if os.path.exists(os.path.join(root, ko)):
        text = read(root, ko)
        text = re.sub(r'"CFBundleDisplayName" = "[^"]*";', '"CFBundleDisplayName" = "YepGram";', text)
        write(root, ko, text)
        print('patched', ko)


def replace_icon(root):
    png = os.path.join(FILES_DIR, 'YepGram.png')
    legacy = os.path.join(root, 'Telegram/Telegram-iOS/DefaultAppIcon.xcassets/AppIconLLC.appiconset/Swiftgram.png')
    if not os.path.exists(legacy):
        failures.append('legacy app icon not found at {}'.format(legacy))
    else:
        shutil.copyfile(png, legacy)
        print('replaced', legacy)

    composer = os.path.join(root, 'Telegram/Telegram-iOS/Swiftgram.icon')
    if not os.path.isdir(composer):
        failures.append('Icon Composer icon not found at {}'.format(composer))
        return
    assets = os.path.join(composer, 'Assets')
    shutil.rmtree(assets, ignore_errors=True)
    os.makedirs(assets)
    shutil.copyfile(png, os.path.join(assets, 'YepGram.png'))
    shutil.copyfile(os.path.join(FILES_DIR, 'icon.json'), os.path.join(composer, 'icon.json'))
    print('replaced', composer)

    # The pill shown next to the Dynamic Island ("SWIFTGRAM" upstream).
    badge = os.path.join(root, 'submodules/TelegramUI/Images.xcassets/Components/AppBadge.imageset/AppBadge@3x.png')
    if not os.path.exists(badge):
        failures.append('app badge not found at {}'.format(badge))
    else:
        shutil.copyfile(os.path.join(FILES_DIR, 'AppBadge@3x.png'), badge)
        print('replaced', badge)


def grey_theme(root):
    path = 'submodules/TelegramUIPreferences/Sources/PresentationThemeSettings.swift'
    replace(root, path,
        'public enum PresentationThemeBaseColor: Int32, CaseIterable {',
        '''// YepGram palette.
public let yepGramNightAccentColor: UInt32 = 0xc9ccdc
public let yepGramNightOutgoingBubbleColor: UInt32 = 0x3a3a3e
public let yepGramDayAccentColor: UInt32 = 0x5b5e70
public let yepGramDayOutgoingBubbleColor: UInt32 = 0xe3e3e8

public enum PresentationThemeBaseColor: Int32, CaseIterable {''')
    replace(root, path,
        '        return PresentationThemeSettings(theme: .builtin(.dayClassic), themePreferredBaseTheme: [:], themeSpecificAccentColors: [:], themeSpecificChatWallpapers: [:],',
        '''        // YepGram: dark grey night theme with a grey accent by default; the day theme gets a darker grey one.
        let nightAccent = PresentationThemeAccentColor(index: 120, baseColor: .preset, accentColor: yepGramNightAccentColor, bubbleColors: [yepGramNightOutgoingBubbleColor], wallpaper: nil)
        let dayAccent = PresentationThemeAccentColor(index: 121, baseColor: .preset, accentColor: yepGramDayAccentColor, bubbleColors: [yepGramDayOutgoingBubbleColor], wallpaper: nil)
        let themeSpecificAccentColors: [Int64: PresentationThemeAccentColor] = [
            PresentationThemeReference.builtin(.night).index: nightAccent,
            PresentationThemeReference.builtin(.dayClassic).index: dayAccent
        ]
        return PresentationThemeSettings(theme: .builtin(.night), themePreferredBaseTheme: [:], themeSpecificAccentColors: themeSpecificAccentColors, themeSpecificChatWallpapers: [:],''')

    # Settings saved by an earlier build keep their own copy of the preset; make the presets follow the palette.
    replace(root, path,
        '        self.themeIndex = decoder.decodeOptionalInt64ForKey("t")\n    }',
        '        self.themeIndex = decoder.decodeOptionalInt64ForKey("t")\n'
        '        // YepGram: the built-in presets always follow the current palette.\n'
        '        if self.baseColor == .preset && self.index == 120 {\n'
        '            self.accentColor = yepGramNightAccentColor\n'
        '            self.bubbleColors = [yepGramNightOutgoingBubbleColor]\n'
        '        } else if self.baseColor == .preset && self.index == 121 {\n'
        '            self.accentColor = yepGramDayAccentColor\n'
        '            self.bubbleColors = [yepGramDayOutgoingBubbleColor]\n'
        '        }\n'
        '    }')

    replace(root, 'submodules/TelegramPresentationData/Sources/DefaultDayPresentationTheme.swift',
        'public let defaultDayAccentColor = UIColor(rgb: 0x0088ff)\n',
        'public let defaultDayAccentColor = UIColor(rgb: 0x5b5e70) // YepGram grey\n')


def keep_deleted_messages(root):
    shutil.copyfile(
        os.path.join(FILES_DIR, 'SyncCore_YepGramDeletedMessageAttribute.swift'),
        os.path.join(root, 'submodules/TelegramCore/Sources/SyncCore/SyncCore_YepGramDeletedMessageAttribute.swift')
    )
    print('added SyncCore_YepGramDeletedMessageAttribute.swift')

    replace(root, 'submodules/TelegramCore/Sources/Account/AccountManager.swift',
        '    declareEncodable(AutoclearTimeoutMessageAttribute.self, f: { AutoclearTimeoutMessageAttribute(decoder: $0) })\n',
        '    declareEncodable(AutoclearTimeoutMessageAttribute.self, f: { AutoclearTimeoutMessageAttribute(decoder: $0) })\n'
        '    declareEncodable(YepGramDeletedMessageAttribute.self, f: { YepGramDeletedMessageAttribute(decoder: $0) })\n')

    path = 'submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift'
    replace(root, path,
        '''            case let .DeleteMessagesWithGlobalIds(ids):
                var resourceIds: [MediaResourceId] = []''',
        '''            case let .DeleteMessagesWithGlobalIds(globalIds):
                // YepGram: keep stored messages the server deleted, marked as deleted.
                var ids: [Int32] = []
                for globalId in globalIds {
                    if let messageId = transaction.messageIdsForGlobalIds([globalId]).first, _internal_yepGramKeepDeletedMessages(transaction: transaction, ids: [messageId]).isEmpty {
                        continue
                    }
                    ids.append(globalId)
                }
                var resourceIds: [MediaResourceId] = []''')
    replace(root, path,
        '''            case let .DeleteMessages(ids):
                _internal_deleteMessages(transaction: transaction, mediaBox: mediaBox, ids: ids, manualAddMessageThreadStatsDifference:''',
        '''            case let .DeleteMessages(allIds):
                // YepGram: keep stored messages the server deleted, marked as deleted.
                let ids = _internal_yepGramKeepDeletedMessages(transaction: transaction, ids: allIds)
                _internal_deleteMessages(transaction: transaction, mediaBox: mediaBox, ids: ids, manualAddMessageThreadStatsDifference:''')


CHAT = 'submodules/TelegramUI/Components/Chat/'


def deleted_mark_in_chat(root):
    path = CHAT + 'ChatMessageDateAndStatusNode/Sources/ChatMessageDateAndStatusNode.swift'
    replace(root, path,
        '        var isPinned: Bool\n        var hasAutoremove: Bool\n',
        '        var isPinned: Bool\n        var isDeleted: Bool\n        var hasAutoremove: Bool\n')
    replace(root, path,
        '            isPinned: Bool,\n            hasAutoremove: Bool,\n',
        '            isPinned: Bool,\n            isDeleted: Bool = false,\n            hasAutoremove: Bool,\n')
    replace(root, path,
        '            self.isPinned = isPinned\n            self.hasAutoremove',
        '            self.isPinned = isPinned\n            self.isDeleted = isDeleted\n            self.hasAutoremove')
    blank = '\n' + ' ' * 12 + '\n'
    replace(root, path,
        '            }' + blank + '            var updatedDateText = arguments.dateText\n',
        '            }' + blank +
        '            // YepGram: a message the server deleted shows a trash icon where the pin would be,\n'
        '            // larger than the pin so it stands out; the extra width is reserved in the layout below.\n'
        '            let yepGramDeletedExtraWidth: CGFloat\n'
        '            if arguments.isDeleted && arguments.replyCount == 0 {\n'
        '                let pinnedSize = graphics.incomingDateAndStatusPinnedIcon.size\n'
        '                let deletedSize = CGSize(width: ceil(pinnedSize.width * 1.4), height: ceil(pinnedSize.height * 1.4))\n'
        '                yepGramDeletedExtraWidth = deletedSize.width - pinnedSize.width\n'
        '                repliesImage = yepGramDeletedIcon(color: dateColor, size: deletedSize)\n'
        '            } else {\n'
        '                yepGramDeletedExtraWidth = 0.0\n'
        '            }' + blank + '            var updatedDateText = arguments.dateText\n')
    replace(root, path,
        '            } else if arguments.isPinned {\n                reactionInset += 12.0',
        '            } else if arguments.isPinned || arguments.isDeleted {\n                reactionInset += 12.0 + yepGramDeletedExtraWidth')
    replace(root, path,
        '                            animation.animator.updateFrame(layer: currentRepliesIcon.layer, frame: repliesIconFrame, completion: nil)\n'
        '                            reactionOffset += 9.0\n',
        '                            animation.animator.updateFrame(layer: currentRepliesIcon.layer, frame: repliesIconFrame, completion: nil)\n'
        '                            reactionOffset += 9.0 + yepGramDeletedExtraWidth\n')
    replace(root, path,
        'private func maybeAddRotationAnimation(',
        '''nonisolated(unsafe) private var yepGramDeletedIconCache: [String: UIImage] = [:]

private func yepGramDeletedIcon(color: UIColor, size: CGSize) -> UIImage? {
    let key = "\\(color.argb)-\\(size.width)x\\(size.height)"
    if let image = yepGramDeletedIconCache[key] {
        return image
    }
    let configuration = UIImage.SymbolConfiguration(pointSize: size.height, weight: .medium)
    guard let symbol = UIImage(systemName: "trash", withConfiguration: configuration)?.withTintColor(color, renderingMode: .alwaysOriginal) else {
        return nil
    }
    let image = generateImage(size, rotatedContext: { size, context in
        context.clear(CGRect(origin: CGPoint(), size: size))
        let scale = min(size.width / symbol.size.width, size.height / symbol.size.height)
        let symbolSize = CGSize(width: symbol.size.width * scale, height: symbol.size.height * scale)
        UIGraphicsPushContext(context)
        symbol.draw(in: CGRect(origin: CGPoint(x: (size.width - symbolSize.width) / 2.0, y: (size.height - symbolSize.height) / 2.0), size: symbolSize))
        UIGraphicsPopContext()
    })
    if let image {
        yepGramDeletedIconCache[key] = image
    }
    return image
}

private func maybeAddRotationAnimation(''')

    # A deleted message is drawn faded, so it reads as gone at a glance.
    path = CHAT + 'ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift'
    replace(root, path,
        '        strongSelf.backgroundNode.setType(type: backgroundType, highlighted: false, graphics: graphics, maskMode: strongSelf.backgroundMaskMode, hasWallpaper: hasWallpaper, transition: legacyTransition, backgroundNode: presentationContext.backgroundNode)\n',
        '        strongSelf.backgroundNode.setType(type: backgroundType, highlighted: false, graphics: graphics, maskMode: strongSelf.backgroundMaskMode, hasWallpaper: hasWallpaper, transition: legacyTransition, backgroundNode: presentationContext.backgroundNode)\n'
        '        // YepGram: a message the server deleted is drawn faded.\n'
        '        strongSelf.mainContainerNode.alpha = item.content.contains(where: { $0.0.yepGramIsDeleted }) ? 0.5 : 1.0\n')

    path = CHAT + 'ChatMessageInteractiveMediaNode/Sources/ChatMessageInteractiveMediaNode.swift'
    replace(root, path,
        '    public var isPinned: Bool\n    public var dateText: String\n',
        '    public var isPinned: Bool\n    public var isDeleted: Bool\n    public var dateText: String\n')
    replace(root, path,
        '        isPinned: Bool,\n        dateText: String\n    ) {',
        '        isPinned: Bool,\n        isDeleted: Bool = false,\n        dateText: String\n    ) {')
    replace(root, path,
        '        self.isPinned = isPinned\n        self.dateText = dateText',
        '        self.isPinned = isPinned\n        self.isDeleted = isDeleted\n        self.dateText = dateText')

    replace(root, CHAT + 'ChatMessageMediaBubbleContentNode/Sources/ChatMessageMediaBubbleContentNode.swift',
        '                    isPinned: item.message.tags.contains(.pinned) && !item.associatedData.isInPinnedListMode && !isReplyThread,\n                    dateText: dateText',
        '                    isPinned: item.message.tags.contains(.pinned) && !item.associatedData.isInPinnedListMode && !isReplyThread,\n                    isDeleted: item.message.yepGramIsDeleted,\n                    dateText: dateText')

    # Every ChatMessageDateAndStatusNode.Arguments(...) call: pass isDeleted right after isPinned.
    sites = {
        'ChatMessageAnimatedStickerItemNode/Sources/ChatMessageAnimatedStickerItemNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageAttachedContentNode/Sources/ChatMessageAttachedContentNode.swift': 'message.yepGramIsDeleted',
        'ChatMessageBubbleItemNode/Sources/ChatMessageBubbleItemNode.swift': 'message.yepGramIsDeleted',
        'ChatMessageContactBubbleContentNode/Sources/ChatMessageContactBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageFactCheckBubbleContentNode/Sources/ChatMessageFactCheckBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageGiveawayBubbleContentNode/Sources/ChatMessageGiveawayBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageInteractiveInstantVideoNode/Sources/ChatMessageInteractiveInstantVideoNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageMapBubbleContentNode/Sources/ChatMessageMapBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessagePollBubbleContentNode/Sources/ChatMessagePollBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageRestrictedBubbleContentNode/Sources/ChatMessageRestrictedBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageRichDataBubbleContentNode/Sources/ChatMessageRichDataBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageStickerItemNode/Sources/ChatMessageStickerItemNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageTextBubbleContentNode/Sources/ChatMessageTextBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageTodoBubbleContentNode/Sources/ChatMessageTodoBubbleContentNode.swift': 'item.message.yepGramIsDeleted',
        'ChatMessageInteractiveFileNode/Sources/ChatMessageInteractiveFileNode.swift': 'arguments.message.yepGramIsDeleted',
        'ChatMessageInteractiveMediaNode/Sources/ChatMessageInteractiveMediaNode.swift': 'dateAndStatus.isDeleted',
    }
    for relative, value in sites.items():
        path = CHAT + relative
        lines = read(root, path).split('\n')
        out = []
        inside = False
        inserted = 0
        for line in lines:
            out.append(line)
            if 'ChatMessageDateAndStatusNode.Arguments(' in line:
                inside = True
            if inside and re.match(r'\s*isPinned: ', line):
                indent = re.match(r'(\s*)', line).group(1)
                out.append('{}isDeleted: {},'.format(indent, value))
                inside = False
                inserted += 1
        if inserted == 0:
            failures.append('{}: no ChatMessageDateAndStatusNode.Arguments isPinned line found'.format(path))
            continue
        write(root, path, '\n'.join(out))
        print('patched', path, '({} call(s))'.format(inserted))


def sideload_app_group(root):
    path = 'submodules/TelegramUI/Sources/AppDelegate.swift'
    group = 'let appGroupName = "group.\\(baseAppBundleId)"'
    replace(root, path,
        '        let baseAppBundleId = Bundle.main.bundleIdentifier!\n        ' + group + '\n\n        let configuration = URLSessionConfiguration.background',
        '        let baseAppBundleId = Bundle.main.bundleIdentifier!\n        let appGroupName = yepGramResolvedAppGroup(baseAppBundleId: baseAppBundleId).name\n\n        let configuration = URLSessionConfiguration.background')
    replace(root, path,
        '        ' + group + '\n        try! PasscodeEnvironment.shared.configure(',
        '        let yepGramAppGroup = yepGramResolvedAppGroup(baseAppBundleId: baseAppBundleId)\n        let appGroupName = yepGramAppGroup.name\n        try! PasscodeEnvironment.shared.configure(')
    replace(root, path,
        '        let maybeAppGroupUrl = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroupName)\n',
        '        let maybeAppGroupUrl = yepGramAppGroup.url\n')
    text = read(root, path)
    with open(os.path.join(FILES_DIR, 'AppDelegate+YepGramAppGroup.swift.txt'), encoding='utf-8') as f:
        helper = f.read()
    write(root, path, text.rstrip('\n') + '\n' + helper)
    print('patched', path, '(app group resolver)')


STRINGS_LINE = re.compile(r'^(\s*"(?:[^"\\]|\\.)*"\s*=\s*")(.*)(";\s*)$')


def rebrand_strings_file(path):
    raw = open(path, 'rb').read()
    for encoding in ('utf-8', 'utf-16'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        failures.append('{}: unknown encoding'.format(path))
        return 0
    changed = 0
    lines = text.split('\n')
    for i, line in enumerate(lines):
        match = STRINGS_LINE.match(line)
        # Only values change; keys stay as the code looks them up.
        if match and 'Swiftgram' in match.group(2):
            lines[i] = match.group(1) + match.group(2).replace('Swiftgram', 'YepGram') + match.group(3)
            changed += 1
    if changed:
        with open(path, 'wb') as f:
            f.write('\n'.join(lines).encode(encoding))
    return changed


def rebrand_texts(root):
    total = 0
    for base in ('Swiftgram/SGStrings/Strings', 'Telegram/Telegram-iOS'):
        for dirpath, _, filenames in os.walk(os.path.join(root, base)):
            for name in filenames:
                if name.endswith('.strings'):
                    total += rebrand_strings_file(os.path.join(dirpath, name))
    print('rebranded {} localized strings'.format(total))

    # Display-only "Swiftgram" literals in code (titles, menu items, "Open in Swiftgram"-style replacements).
    literals = 0
    for base in ('submodules', 'Swiftgram'):
        for dirpath, _, filenames in os.walk(os.path.join(root, base)):
            for name in filenames:
                if not name.endswith('.swift'):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding='utf-8', newline='') as f:
                    text = f.read()
                if '"Swiftgram"' not in text:
                    continue
                literals += text.count('"Swiftgram"')
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(text.replace('"Swiftgram"', '"YepGram"'))
    if literals == 0:
        failures.append('no "Swiftgram" literals found in code')
    print('rebranded {} code literals'.format(literals))


def branded_icons(root):
    # Settings row icon and context-menu glyph keep their asset names; only the images change.
    assets = os.path.join(root, 'Swiftgram/SGSettingsUI/Images.xcassets')
    for imageset, filename, scale in (('SwiftgramSettings.imageset', 'YepGramSettings.png', '1x'), ('SwiftgramContextMenu.imageset', 'YepGramContextMenu@3x.png', '3x')):
        folder = os.path.join(assets, imageset)
        if not os.path.isdir(folder):
            failures.append('asset not found: {}'.format(folder))
            continue
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
        shutil.copyfile(os.path.join(FILES_DIR, filename), os.path.join(folder, filename))
        with open(os.path.join(folder, 'Contents.json'), 'w', encoding='utf-8') as f:
            f.write('{\n  "images" : [\n    {\n      "filename" : "%s",\n      "idiom" : "universal",\n      "scale" : "%s"\n    }\n  ],\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n' % (filename, scale))
        print('replaced', folder)

    # Alternate app icons: only YepGram's own is offered.
    alticon = os.path.join(root, 'Telegram/Telegram-iOS/SGDefault.alticon')
    for name in ('SGDefault@2x.png', 'SGDefault@3x.png'):
        shutil.copyfile(os.path.join(FILES_DIR, name), os.path.join(alticon, name))
    path = 'submodules/TelegramUI/Sources/AppDelegate.swift'
    text = read(root, path)
    pattern = re.compile(r'                icons = \[\n                    PresentationAppIcon\(name: "SGDefault".*?\n                \]\n', re.S)
    text, n = pattern.subn('                icons = [\n                    PresentationAppIcon(name: "SGDefault", imageName: "SGDefault", isDefault: true),\n                ]\n', text)
    if n != 1:
        failures.append('{}: alternate icon list not found'.format(path))
    else:
        write(root, path, text)
        print('patched', path, '(one app icon)')


def remove_swiftgram_pro(root):
    path = 'Swiftgram/SGPeerInfoRows/Sources/SGPeerInfoRows.swift'
    text = read(root, path)
    pattern = re.compile(r'func sgPeerInfoSettingsItems\(context: AccountContext, paymentsEnabled: Bool, presentationData: PresentationData, interaction: PeerInfoInteraction\) -> \[PeerInfoScreenItem\] \{\n.*?\n\}\n', re.S)
    text, n = pattern.subn(
        'func sgPeerInfoSettingsItems(context: AccountContext, paymentsEnabled: Bool, presentationData: PresentationData, interaction: PeerInfoInteraction) -> [PeerInfoScreenItem] {\n'
        '    // YepGram: one settings entry, no Swiftgram Pro.\n'
        '    return [PeerInfoScreenDisclosureItem(id: 1, label: .none, text: "YepGram", icon: PresentationResourcesSettings.swiftgram, action: {\n'
        '        interaction.openSettings(.swiftgram)\n'
        '    })]\n'
        '}\n', text)
    if n != 1:
        failures.append('{}: sgPeerInfoSettingsItems not found'.format(path))
    else:
        write(root, path, text)
        print('patched', path, '(no Pro row)')

    # Every Pro upsell goes through the paywall factory; without a paywall they do nothing.
    path = 'submodules/TelegramUI/Sources/SharedAccountContext.swift'
    replace(root, path,
        '        guard let sgIAP = self.SGIAP else {',
        '        guard yepGramSwiftgramProEnabled(), let sgIAP = self.SGIAP else {')
    text = read(root, path)
    write(root, path, text.rstrip('\n') + '\n\n// YepGram ships without Swiftgram Pro.\nprivate func yepGramSwiftgramProEnabled() -> Bool {\n    return false\n}\n')


def ghost_mode(root):
    shutil.copyfile(os.path.join(FILES_DIR, 'YepGramSettings.swift'), os.path.join(root, 'Swiftgram/SGSimpleSettings/Sources/YepGramSettings.swift'))
    print('added YepGramSettings.swift')
    state = 'submodules/TelegramCore/Sources/State/'
    for name in ('SynchronizePeerReadState.swift', 'ManagedAccountPresence.swift', 'ManagedLocalInputActivities.swift', 'ManagedSynchronizeConsumeMessageContentsOperations.swift'):
        replace(root, state + name, 'import SwiftSignalKit\n', 'import SwiftSignalKit\nimport SGSimpleSettings\n')

    header = 'private func pushPeerReadState(network: Network, postbox: Postbox, stateManager: AccountStateManager, peerId: PeerId, readState: PeerReadState) -> Signal<PeerReadState, PeerReadStateValidationError> {\n'
    replace(root, state + 'SynchronizePeerReadState.swift', header,
        header + '    // YepGram ghost mode: the read mark stays local, so the sender is never told.\n'
        '    if YepGramSettings.ghost(.noReadReceipts, accountId: stateManager.accountPeerId.id._internalGetInt64Value()) {\n        return .single(readState)\n    }\n')

    header = 'private func synchronizeConsumeMessageContents(transaction: Transaction, network: Network, stateManager: AccountStateManager, peerId: PeerId, operation: SynchronizeConsumeMessageContentsOperation) -> Signal<Void, NoError> {\n'
    replace(root, state + 'ManagedSynchronizeConsumeMessageContentsOperations.swift', header,
        header + '    // YepGram ghost mode: "listened"/"watched" is a read receipt too.\n'
        '    if YepGramSettings.ghost(.noReadReceipts, accountId: stateManager.accountPeerId.id._internalGetInt64Value()) {\n        return .complete()\n    }\n')

    replace(root, state + 'ManagedAccountPresence.swift',
        '    private func updatePresence(_ isOnline: Bool) {\n',
        '    private func updatePresence(_ requestedOnline: Bool) {\n'
        '        // YepGram ghost mode: always report offline. Read on every refresh, so toggling applies at the next one.\n'
        '        let isOnline = requestedOnline && !YepGramSettings.ghost(.hideOnline, accountId: self.accountPeerId.id._internalGetInt64Value())\n')

    header = 'private func requestActivity(postbox: Postbox, network: Network, accountPeerId: PeerId, peerId: PeerId, threadId: Int64?, activity: PeerInputActivity?) -> Signal<Void, NoError> {\n'
    replace(root, state + 'ManagedLocalInputActivities.swift', header,
        header + '    // YepGram ghost mode: no "typing…" and similar activity.\n'
        '    if YepGramSettings.ghost(.noTyping, accountId: accountPeerId.id._internalGetInt64Value()) {\n        return .complete()\n    }\n')


def yepgram_settings_ui(root):
    path = 'Swiftgram/SGSettingsUI/Sources/SGSettingsController.swift'
    replace(root, path, 'import UndoUI\n', 'import UndoUI\nimport UserNotifications\n')
    replace(root, path, '    case search\n    case trending\n',
        '    case search\n    case yepCategories\n    case yepLinks\n    case yepGhost\n    case yepDeleted\n    case yepAccount\n    case trending\n')
    replace(root, path, '    case hideAccountInNotifications\n}',
        '    case hideAccountInNotifications\n    case yepGhostNoReadReceipts\n    case yepGhostHideOnline\n    case yepGhostNoTyping\n    case yepKeepDeletedMessages\n    case yepAccountInAppNotifications\n}')
    replace(root, path, '    case contentSettings\n    case languageSettings\n}',
        '    case contentSettings\n    case languageSettings\n'
        '    case yepCategoryYepGram\n    case yepCategoryAccounts\n    case yepCategoryTools\n    case yepCategoryGeneral\n'
        '    case yepCategoryAppearance\n    case yepCategoryChats\n    case yepCategoryOther\n    case yepChannel\n    case yepSource\n}')

    replace(root, path, 'private func SGControllerEntries(presentationData: PresentationData, callListSettings: CallListSettings, experimentalUISettings: ExperimentalUISettings, appConfiguration: AppConfiguration, nameColors: PeerNameColors, state: SGSettingsControllerState) -> [SGControllerEntry] {\n',
        '''// YepGram strings: Russian for a Russian interface, English otherwise.
private func yepGramText(_ lang: String, _ ru: String, _ en: String) -> String {
    return lang == "ru" ? ru : en
}

// YepGram: settings are split into categories; the root lists them, each category opens its own screen.
private enum YepGramSettingsCategory: CaseIterable {
    case yepGram
    case accounts
    case general
    case appearance
    case chats
    case other

    func title(_ lang: String) -> String {
        switch self {
        case .yepGram:
            return "YepGram"
        case .accounts:
            return yepGramText(lang, "Аккаунты", "Accounts")
        case .general:
            return yepGramText(lang, "Основные", "General")
        case .appearance:
            return yepGramText(lang, "Оформление", "Appearance")
        case .chats:
            return yepGramText(lang, "Чаты", "Chats")
        case .other:
            return yepGramText(lang, "Другое", "Other")
        }
    }

    var sections: [SGControllerSection] {
        switch self {
        case .yepGram:
            return [.yepGhost, .yepDeleted]
        case .accounts:
            return [.yepAccount]
        case .general:
            return [.tabs, .folders, .chatList, .profiles, .stories]
        case .appearance:
            return [.trending, .stickers, .accountColors]
        case .chats:
            return [.translation, .voiceMessages, .calls, .photo, .videoNotes, .contextMenu]
        case .other:
            return [.content, .other]
        }
    }

    var link: SGDisclosureLink {
        switch self {
        case .yepGram:
            return .yepCategoryYepGram
        case .accounts:
            return .yepCategoryAccounts
        case .general:
            return .yepCategoryGeneral
        case .appearance:
            return .yepCategoryAppearance
        case .chats:
            return .yepCategoryChats
        case .other:
            return .yepCategoryOther
        }
    }
}

// A category shows its own sections; the root shows the search field, the categories and the links,
// or every matching setting while a search query is typed.
private func yepGramFilterEntries(entries: [SGControllerEntry], category: YepGramSettingsCategory?, searchQuery: String?, lang: String) -> [SGControllerEntry] {
    if let category {
        let sections = Set(category.sections.map { $0.rawValue })
        return entries.filter { sections.contains($0.section) }
    }
    if let searchQuery, !searchQuery.isEmpty {
        return filterSGItemListUIEntrires(entries: entries, by: searchQuery)
    }
    var result = entries.filter { $0.section == SGControllerSection.search.rawValue }
    var id = 1_000_000
    result.append(.header(id: id, section: .yepCategories, text: yepGramText(lang, "КАТЕГОРИИ", "CATEGORIES"), badge: nil))
    for category in YepGramSettingsCategory.allCases {
        id += 1
        result.append(.disclosure(id: id, section: .yepCategories, link: category.link, text: category.title(lang)))
        if category == .accounts {
            id += 1
            result.append(.disclosure(id: id, section: .yepCategories, link: .yepCategoryTools, text: yepGramText(lang, "Инструменты", "Tools")))
        }
    }
    id += 1
    result.append(.header(id: id, section: .yepLinks, text: yepGramText(lang, "ССЫЛКИ", "LINKS"), badge: nil))
    id += 1
    result.append(.disclosure(id: id, section: .yepLinks, link: .yepChannel, text: yepGramText(lang, "Канал @yepgramoff", "Channel @yepgramoff")))
    id += 1
    result.append(.disclosure(id: id, section: .yepLinks, link: .yepSource, text: yepGramText(lang, "Исходный код", "Source code")))
    return result
}

private func SGControllerEntries(presentationData: PresentationData, callListSettings: CallListSettings, experimentalUISettings: ExperimentalUISettings, appConfiguration: AppConfiguration, nameColors: PeerNameColors, state: SGSettingsControllerState, category: YepGramSettingsCategory?, accountId: Int64) -> [SGControllerEntry] {
''')

    search = '    entries.append(.searchInput(id: id.count, section: .search, title: NSAttributedString(string: "🔍"), text: state.searchQuery ?? "", placeholder: strings.Common_Search))\n'
    replace(root, path, search, search +
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepGhost, text: yepGramText(lang, "РЕЖИМ ПРИЗРАКА", "GHOST MODE"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostNoReadReceipts, value: YepGramSettings.ghost(.noReadReceipts, accountId: accountId), text: yepGramText(lang, "Не отправлять «прочитано»", "Don\'t send read receipts"), enabled: true))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostHideOnline, value: YepGramSettings.ghost(.hideOnline, accountId: accountId), text: yepGramText(lang, "Не показывать «в сети»", "Hide online status"), enabled: true))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostNoTyping, value: YepGramSettings.ghost(.noTyping, accountId: accountId), text: yepGramText(lang, "Не отправлять «печатает…»", "Don\'t send typing status"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepGhost, text: yepGramText(lang, "Собеседники не увидят, что вы прочитали их сообщения, прослушали голосовые, были в сети или печатаете. Если вы сами напишете в чат, Telegram отметит его прочитанным.", "Others won\'t see that you read their messages, played voice messages, were online or are typing. Sending a message to a chat still marks it read.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepDeleted, text: yepGramText(lang, "УДАЛЁННЫЕ СООБЩЕНИЯ", "DELETED MESSAGES"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepDeleted, settingName: .yepKeepDeletedMessages, value: YepGramSettings.keepDeletedMessages, text: yepGramText(lang, "Сохранять удалённые сообщения", "Keep deleted messages"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepDeleted, text: yepGramText(lang, "Сообщения, которые удалил собеседник, остаются в чате полупрозрачными и с корзиной у времени.", "Messages others delete stay in the chat, faded, with a trash mark next to the time.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepAccount, text: yepGramText(lang, "ЭТОТ АККАУНТ", "THIS ACCOUNT"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepAccount, settingName: .yepAccountInAppNotifications, value: !YepGramSettings.isInAppNotificationsMuted(accountId: accountId), text: yepGramText(lang, "Уведомления в приложении", "In-app notifications"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepAccount, text: yepGramText(lang, "Баннеры о новых сообщениях, пока YepGram открыт. У каждого аккаунта настройка своя: чтобы поменять её для другого, переключитесь на него.", "Banners for new messages while YepGram is open. Each account has its own setting: switch to another account to change it there.")))\n')

    # Account-wide switches that already exist move into the Accounts category.
    replace(root, path, 'section: .other, settingName: .hidePhoneInSettings,', 'section: .yepAccount, settingName: .hidePhoneInSettings,')
    replace(root, path, 'entries.append(.notice(id: id.count, section: .other, text: i18n("Settings.HidePhoneInSettingsUI.Notice", lang)))',
        'entries.append(.notice(id: id.count, section: .yepAccount, text: i18n("Settings.HidePhoneInSettingsUI.Notice", lang)))')
    replace(root, path, 'section: .other, settingName: .hideAccountInNotifications,', 'section: .yepAccount, settingName: .hideAccountInNotifications,')

    replace(root, path, '    return filterSGItemListUIEntrires(entries: entries, by: state.searchQuery)\n',
        '    return yepGramFilterEntries(entries: entries, category: category, searchQuery: state.searchQuery, lang: lang)\n')

    replace(root, path, 'public func sgSettingsController(context: AccountContext/*, focusOnItemTag: Int? = nil*/) -> ViewController {\n',
        'public func sgSettingsController(context: AccountContext/*, focusOnItemTag: Int? = nil*/) -> ViewController {\n'
        '    return yepGramSettingsController(context: context, category: nil)\n'
        '}\n\n'
        'private func yepGramSettingsController(context: AccountContext, category: YepGramSettingsCategory?) -> ViewController {\n')

    toggles = ('        case .hideAccountInNotifications:\n'
               '            SGSimpleSettings.shared.hideAccountInNotifications = value\n'
               '            SGSimpleSettings.shared.synchronizeShared()\n')
    replace(root, path, toggles, toggles +
        '        case .yepGhostNoReadReceipts:\n'
        '            YepGramSettings.setGhost(.noReadReceipts, accountId: yepGramTargetAccountId, value)\n'
        '            simplePromise.set(true)\n'
        '        case .yepGhostHideOnline:\n'
        '            YepGramSettings.setGhost(.hideOnline, accountId: yepGramTargetAccountId, value)\n'
        '            simplePromise.set(true)\n'
        '        case .yepGhostNoTyping:\n'
        '            YepGramSettings.setGhost(.noTyping, accountId: yepGramTargetAccountId, value)\n'
        '            simplePromise.set(true)\n'
        '        case .yepKeepDeletedMessages:\n'
        '            YepGramSettings.keepDeletedMessages = value\n'
        '            simplePromise.set(true)\n'
        '        case .yepAccountInAppNotifications:\n'
        '            YepGramSettings.setInAppNotificationsMuted(!value, accountId: context.account.peerId.id._internalGetInt64Value())\n'
        '            simplePromise.set(true)\n')

    links = ('            case .languageSettings:\n'
             '                pushControllerImpl?(context.sharedContext.makeLocalizationListController(context: context))\n')
    replace(root, path, links, links +
        '            case .yepCategoryYepGram:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .yepGram))\n'
        '            case .yepCategoryAccounts:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .accounts))\n'
        '            case .yepCategoryTools:\n'
        '                pushControllerImpl?(context.sharedContext.makeSGProController(context: context))\n'
        '            case .yepCategoryGeneral:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .general))\n'
        '            case .yepCategoryAppearance:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .appearance))\n'
        '            case .yepCategoryChats:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .chats))\n'
        '            case .yepCategoryOther:\n'
        '                pushControllerImpl?(yepGramSettingsController(context: context, category: .other))\n'
        '            case .yepChannel:\n'
        '                context.sharedContext.applicationBindings.openUrl(YepGramSettings.channelUrl)\n'
        '            case .yepSource:\n'
        '                context.sharedContext.applicationBindings.openUrl(YepGramSettings.sourceUrl)\n')

    replace(root, path,
        '        let entries = SGControllerEntries(presentationData: presentationData, callListSettings: callListSettings, experimentalUISettings: experimentalUISettings, appConfiguration: appConfiguration, nameColors: PeerNameColors.with(availableReplyColors: availableReplyColors, availableProfileColors: availableProfileColors), state: state)\n',
        '        let entries = SGControllerEntries(presentationData: presentationData, callListSettings: callListSettings, experimentalUISettings: experimentalUISettings, appConfiguration: appConfiguration, nameColors: PeerNameColors.with(availableReplyColors: availableReplyColors, availableProfileColors: availableProfileColors), state: state, category: category, accountId: context.account.peerId.id._internalGetInt64Value())\n')
    replace(root, path, 'title: .text("YepGram"), leftNavigationButton: nil',
        'title: .text(category?.title(presentationData.strings.baseLanguageCode) ?? "YepGram"), leftNavigationButton: nil')


def unlock_swiftgram_pro_features(root):
    # Swiftgram's paid features run on the device; YepGram treats every install as entitled.
    path = 'Swiftgram/SGStatus/Sources/SGStatus.swift'
    replace(root, path, '        return SGStatus(status: 1)\n', '        return SGStatus(status: 2)\n')
    replace(root, path, '    public init(status: Int64) {\n        self.status = status\n    }',
        '    public init(status: Int64) {\n        // YepGram: Swiftgram Pro features are free.\n        self.status = max(status, 2)\n    }')
    replace(root, path, '        self.status = try container.decodeIfPresent(Int64.self, forKey: "status") ?? 1\n',
        '        let decodedStatus = try container.decodeIfPresent(Int64.self, forKey: "status") ?? 2\n'
        '        self.status = max(decodedStatus, 2)\n')
    replace(root, 'Swiftgram/SGSimpleSettings/Sources/SimpleSettings.swift', '        Keys.status.rawValue: 1,\n', '        Keys.status.rawValue: 2,\n')

    # The former Pro screen becomes "Tools", without Swiftgram's icons and badges.
    path = 'Swiftgram/SGProUI/Sources/SGProUI.swift'
    replace(root, path,
        '    entries.append(.header(id: id.count, section: .appearance, text: presentationData.strings.Appearance_Title.uppercased(), badge: nil))\n'
        '    entries.append(.disclosure(id: id.count, section: .appearance, link: .appIcons, text: presentationData.strings.Appearance_AppIcon))\n'
        '    entries.append(.disclosure(id: id.count, section: .appearance, link: .appBages, text: "AppBadge.Title".i18n(lang)))\n'
        '    entries.append(.notice(id: id.count, section: .appearance, text: "AppBadge.Notice".i18n(lang)))\n', '')
    replace(root, path, 'title: .text("Swiftgram Pro")',
        'title: .text(presentationData.strings.baseLanguageCode == "ru" ? "Инструменты" : "Tools")')


def per_account_in_app_notifications(root):
    path = 'submodules/TelegramUI/Sources/ApplicationContext.swift'
    replace(root, path, 'import SGStrings\n', 'import SGStrings\nimport SGSimpleSettings\n')
    anchor = ('        |> deliverOn(Queue.mainQueue())).start(next: { [weak self] messageList in\n'
              '            if messageList.isEmpty {\n'
              '                return\n'
              '            }\n')
    replace(root, path, anchor, anchor +
        '            // YepGram: in-app banners can be switched off for one account.\n'
        '            if let strongSelf = self, YepGramSettings.isInAppNotificationsMuted(accountId: strongSelf.context.account.peerId.id._internalGetInt64Value()) {\n'
        '                return\n'
        '            }\n')


def intro_logo(root):
    folder = os.path.join(root, 'Telegram/Telegram-iOS/Resources/intro')
    if not os.path.isdir(folder):
        failures.append('intro textures not found at {}'.format(folder))
        return
    # The intro draws the plane over the sphere; YepGram's sphere is the whole icon and the plane is empty.
    shutil.copyfile(os.path.join(FILES_DIR, 'intro_telegram_sphere@2x.png'), os.path.join(folder, 'telegram_sphere@2x.png'))
    shutil.copyfile(os.path.join(FILES_DIR, 'intro_telegram_plane1@2x.png'), os.path.join(folder, 'telegram_plane1@2x.png'))
    print('replaced intro logo')

def edit_history(root):
    shutil.copyfile(os.path.join(FILES_DIR, 'SyncCore_YepGramEditHistoryAttribute.swift'),
                    os.path.join(root, 'submodules/TelegramCore/Sources/SyncCore/SyncCore_YepGramEditHistoryAttribute.swift'))
    print('added SyncCore_YepGramEditHistoryAttribute.swift')

    registered = '    declareEncodable(YepGramDeletedMessageAttribute.self, f: { YepGramDeletedMessageAttribute(decoder: $0) })\n'
    replace(root, 'submodules/TelegramCore/Sources/Account/AccountManager.swift', registered,
        registered + '    declareEncodable(YepGramEditHistoryAttribute.self, f: { YepGramEditHistoryAttribute(decoder: $0) })\n')

    replace(root, 'submodules/TelegramCore/Sources/State/AccountStateManagementUtils.swift',
        '                    return .update(mergedServerMessageUpdate(previous: previousMessage, updated: message))\n',
        '                    // YepGram: keep the text an edit replaces.\n'
        '                    return .update(_internal_yepGramWithEditHistory(previous: previousMessage, updated: mergedServerMessageUpdate(previous: previousMessage, updated: message)))\n')

    path = 'submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift'
    json_action = ('        if SGSimpleSettings.shared.contextShowJson {\n'
                   '            actions.append(showJsonAction)\n'
                   '        } else {\n'
                   '            sgActions.append(showJsonAction)\n'
                   '        }\n')
    replace(root, path, json_action, json_action +
        '        // YepGram: the earlier texts of an edited message.\n'
        '        if let editHistory = message.attributes.first(where: { $0 is YepGramEditHistoryAttribute }) as? YepGramEditHistoryAttribute, !editHistory.texts.isEmpty {\n'
        '            let isRussian = chatPresentationInterfaceState.strings.baseLanguageCode == "ru"\n'
        '            let historyTitle = isRussian ? "История изменений" : "Edit history"\n'
        '            actions.append(.action(ContextMenuActionItem(text: historyTitle, icon: { theme in\n'
        '                return generateTintedImage(image: UIImage(bundleImageName: "Chat/Context Menu/Edit"), color: theme.actionSheet.primaryTextColor)\n'
        '            }, action: { c, _ in\n'
        '                c?.dismiss(completion: {\n'
        '                    let presentationData = context.sharedContext.currentPresentationData.with { $0 }\n'
        '                    let formatter = DateFormatter()\n'
        '                    formatter.dateStyle = .short\n'
        '                    formatter.timeStyle = .short\n'
        '                    var versions: [String] = []\n'
        '                    for (index, text) in editHistory.texts.enumerated().reversed() {\n'
        '                        let date = index < editHistory.dates.count ? editHistory.dates[index] : 0\n'
        '                        versions.append(formatter.string(from: Date(timeIntervalSince1970: Double(date))) + "\\n" + text)\n'
        '                    }\n'
        '                    controllerInteraction.presentController(textAlertController(context: context, title: historyTitle, text: versions.joined(separator: "\\n\\n"), actions: [TextAlertAction(type: .defaultAction, title: presentationData.strings.Common_OK, action: {})]), nil)\n'
        '                })\n'
        '            })))\n'
        '        }\n')

    path = 'Swiftgram/SGSettingsUI/Sources/SGSettingsController.swift'
    replace(root, path, '    case yepAccountInAppNotifications\n}', '    case yepAccountInAppNotifications\n    case yepKeepEditHistory\n}')
    deleted_notice = ('    entries.append(.notice(id: id.count, section: .yepDeleted, text: yepGramText(lang, "Сообщения, которые удалил собеседник, остаются в чате полупрозрачными и с корзиной у времени.", "Messages others delete stay in the chat, faded, with a trash mark next to the time.")))\n')
    replace(root, path, deleted_notice, deleted_notice +
        '    entries.append(.toggle(id: id.count, section: .yepDeleted, settingName: .yepKeepEditHistory, value: YepGramSettings.keepEditHistory, text: yepGramText(lang, "Сохранять историю изменений", "Keep edit history"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepDeleted, text: yepGramText(lang, "Прошлые версии изменённых сообщений: удержите сообщение и выберите «История изменений».", "Earlier versions of edited messages: long-press a message and choose Edit history.")))\n')
    toggle = ('        case .yepAccountInAppNotifications:\n'
              '            YepGramSettings.setInAppNotificationsMuted(!value, accountId: context.account.peerId.id._internalGetInt64Value())\n'
              '            simplePromise.set(true)\n')
    replace(root, path, toggle, toggle +
        '        case .yepKeepEditHistory:\n'
        '            YepGramSettings.keepEditHistory = value\n'
        '            simplePromise.set(true)\n')



def ghost_extras(root):
    shutil.copyfile(os.path.join(FILES_DIR, 'YepGramGhost.swift'), os.path.join(root, 'submodules/TelegramCore/Sources/State/YepGramGhost.swift'))
    print('added YepGramGhost.swift')

    # Read after action: sending, reacting and voting.
    header = 'public func enqueueMessages(account: Account, peerId: PeerId, messages: [EnqueueMessage]) -> Signal<[MessageId?], NoError> {\n'
    replace(root, 'submodules/TelegramCore/Sources/PendingMessages/EnqueueMessage.swift', header,
        header + '    _internal_yepGramReadAfterAction(account: account, peerId: peerId)\n')
    header = 'public func updateMessageReactionsInteractively(account: Account, messageIds: [MessageId], reactions: [UpdateMessageReaction], isLarge: Bool, storeAsRecentlyUsed: Bool, add: Bool = false) -> Signal<Never, NoError> {\n'
    replace(root, 'submodules/TelegramCore/Sources/State/MessageReactions.swift', header,
        header + '    if let peerId = messageIds.first?.peerId {\n        _internal_yepGramReadAfterAction(account: account, peerId: peerId)\n    }\n')
    header = 'func _internal_requestMessageSelectPollOption(account: Account, messageId: MessageId, opaqueIdentifiers: [Data]) -> Signal<TelegramMediaPoll?, RequestMessageSelectPollOptionError> {\n'
    replace(root, 'submodules/TelegramCore/Sources/TelegramEngine/Messages/Polls.swift', header,
        header + '    _internal_yepGramReadAfterAction(account: account, peerId: messageId.peerId)\n')

    # Settings switch for it, under the ghost switches.
    path = 'Swiftgram/SGSettingsUI/Sources/SGSettingsController.swift'
    replace(root, path, '    case yepKeepEditHistory\n}', '    case yepKeepEditHistory\n    case yepGhostReadAfterAction\n}')
    typing = '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostNoTyping, value: YepGramSettings.ghost(.noTyping, accountId: accountId), text: yepGramText(lang, "Не отправлять «печатает…»", "Don\'t send typing status"), enabled: true))\n'
    replace(root, path, typing, typing +
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostReadAfterAction, value: YepGramSettings.ghost(.readAfterAction, accountId: accountId), text: yepGramText(lang, "Прочитать после действия", "Read after action"), enabled: YepGramSettings.ghost(.noReadReceipts, accountId: accountId)))\n'
        '    entries.append(.notice(id: id.count, section: .yepGhost, text: yepGramText(lang, "Если вы ответили, поставили реакцию или проголосовали в чате, он отмечается прочитанным, чтобы собеседник не видел ответа без «прочитано».", "Replying, reacting or voting in a chat marks it read, so others don\'t see an answer without a read mark.")))\n')
    toggle = ('        case .yepKeepEditHistory:\n'
              '            YepGramSettings.keepEditHistory = value\n'
              '            simplePromise.set(true)\n')
    replace(root, path, toggle, toggle +
        '        case .yepGhostReadAfterAction:\n'
        '            YepGramSettings.setGhost(.readAfterAction, accountId: yepGramTargetAccountId, value)\n'
        '            simplePromise.set(true)\n')

    # Ghost mode from the Chats tab, and 👻 in the title while it is on.
    path = 'submodules/ChatListUI/Sources/ChatListController.swift'
    replace(root, path,
        '            var items: [ContextMenuItem] = []\n'
        '            items.append(.action(ContextMenuActionItem(text: hasFolders ? strongSelf.presentationData.strings.ChatList_EditFolders',
        '            var items: [ContextMenuItem] = []\n'
        '            // YepGram: ghost mode on and off from the Chats tab.\n'
        '            let yepGramAccountId = strongSelf.context.account.peerId.id._internalGetInt64Value()\n'
        '            let yepGramGhostOn = YepGramSettings.isGhostModeOn(accountId: yepGramAccountId)\n'
        '            let yepGramIsRussian = strongSelf.presentationData.strings.baseLanguageCode == "ru"\n'
        '            items.append(.action(ContextMenuActionItem(text: yepGramGhostOn ? (yepGramIsRussian ? "Выключить режим призрака" : "Turn off ghost mode") : (yepGramIsRussian ? "Включить режим призрака" : "Turn on ghost mode"), icon: { theme in\n'
        '                return generateTintedImage(image: UIImage(bundleImageName: yepGramGhostOn ? "Chat/Context Menu/Eye" : "Chat/Context Menu/EyeLocked"), color: theme.contextMenu.primaryColor)\n'
        '            }, action: { _, f in\n'
        '                YepGramSettings.setGhostMode(!yepGramGhostOn, accountId: yepGramAccountId)\n'
        '                f(.dismissWithoutContent)\n'
        '            })))\n'
        '            items.append(.separator)\n'
        '            items.append(.action(ContextMenuActionItem(text: hasFolders ? strongSelf.presentationData.strings.ChatList_EditFolders')
    replace(root, path,
        '            if groupId == .root {\n                defaultTitle = presentationData.strings.DialogList_Title\n',
        '            if groupId == .root {\n                // YepGram: account tag and 👻 in title.\n'
        '                let yepGramAccountId = self.context.account.peerId.id._internalGetInt64Value()\n'
        '                let yepGramTag = YepGramSettings.accountLabel(accountId: yepGramAccountId)\n'
        '                let yepGramTagText = yepGramTag.isEmpty ? "" : " [\\(yepGramTag)]"\n'
        '                let yepGramGhostText = YepGramSettings.isGhostModeOn(accountId: yepGramAccountId) ? " 👻" : ""\n'
        '                defaultTitle = presentationData.strings.DialogList_Title + yepGramTagText + yepGramGhostText\n')


def message_ids_in_menu(root):
    path = 'submodules/TelegramUI/Sources/ChatInterfaceStateContextMenus.swift'
    anchor = '        // YepGram: the earlier texts of an edited message.\n'
    replace(root, path, anchor,
        '        // YepGram: chat and message IDs, copied on tap.\n'
        '        do {\n'
        '            let isRussian = chatPresentationInterfaceState.strings.baseLanguageCode == "ru"\n'
        '            let rawPeerId = message.id.peerId.id._internalGetInt64Value()\n'
        '            let chatId: String\n'
        '            if message.id.peerId.namespace == Namespaces.Peer.CloudChannel {\n'
        '                chatId = "-100\\(rawPeerId)"\n'
        '            } else if message.id.peerId.namespace == Namespaces.Peer.CloudGroup {\n'
        '                chatId = "-\\(rawPeerId)"\n'
        '            } else {\n'
        '                chatId = "\\(rawPeerId)"\n'
        '            }\n'
        '            let idsText = (isRussian ? "ID чата: " : "Chat ID: ") + chatId + "\\n" + (isRussian ? "ID сообщения: " : "Message ID: ") + "\\(message.id.id)"\n'
        '            sgActions.append(.action(ContextMenuActionItem(text: isRussian ? "Скопировать ID" : "Copy IDs", icon: { theme in\n'
        '                return generateTintedImage(image: UIImage(bundleImageName: "Chat/Context Menu/Copy"), color: theme.actionSheet.primaryTextColor)\n'
        '            }, action: { _, f in\n'
        '                UIPasteboard.general.string = idsText\n'
        '                f(.default)\n'
        '            })))\n'
        '        }\n' + anchor)


def developer_badge(root):
    folder = os.path.join(root, 'submodules/TelegramUI/Images.xcassets/YepGram/DeveloperBadge.imageset')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(root, 'submodules/TelegramUI/Images.xcassets/YepGram/Contents.json'), 'w', encoding='utf-8') as f:
        f.write('{\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  },\n  "properties" : {\n    "provides-namespace" : true\n  }\n}\n')
    shutil.copyfile(os.path.join(FILES_DIR, 'YepGramDeveloperBadge@3x.png'), os.path.join(folder, 'DeveloperBadge@3x.png'))
    with open(os.path.join(folder, 'Contents.json'), 'w', encoding='utf-8') as f:
        f.write('{\n  "images" : [\n    {\n      "filename" : "DeveloperBadge@3x.png",\n      "idiom" : "universal",\n      "scale" : "3x"\n    }\n  ],\n  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n')
    print('added developer badge image')

    # Chat list rows: the badge takes the verified mark's place.
    path = 'submodules/ChatListUI/Sources/Node/ChatListItem.swift'
    text = read(root, path)
    pattern = re.compile(r'(?P<indent>[ ]+)currentCredibilityIconContent = \.verified\(fillColor: item\.presentationData\.theme\.list\.itemCheckColors\.fillColor, foregroundColor: item\.presentationData\.theme\.list\.itemCheckColors\.foregroundColor, sizeType: \.compact\)\n(?P<close>[ ]+)\}\n')
    def add_badge(m):
        indent = m.group('close')
        return (m.group(0) +
                indent + 'if yepGramIsDeveloper(peer.id) {\n' +
                indent + '    currentCredibilityIconContent = .image(image: UIImage(bundleImageName: "YepGram/DeveloperBadge"), tintColor: nil)\n' +
                indent + '}\n')
    text, n = pattern.subn(add_badge, text)
    if n == 0:
        failures.append('{}: verified mark not found'.format(path))
    else:
        write(root, path, text)
        print('patched', path, '({} places)'.format(n))

    # Profile header: shown where the verification mark would be.
    path = 'submodules/TelegramUI/Components/PeerInfo/PeerInfoScreen/Sources/PeerInfoHeaderNode.swift'
    text = read(root, path)
    start = text.find('            switch verifiedIcon {\n')
    default = ('            default:\n'
               '                emojiRegularStatusContent = .none\n'
               '                emojiExpandedStatusContent = .none\n')
    at = text.find(default, start) if start >= 0 else -1
    if at < 0:
        failures.append('{}: verified icon switch not found'.format(path))
    else:
        text = text[:at] + (
            '            default:\n'
            '                // YepGram: the developer badge.\n'
            '                if let peer, yepGramIsDeveloper(peer.id), let yepGramBadge = UIImage(bundleImageName: "YepGram/DeveloperBadge") {\n'
            '                    emojiRegularStatusContent = .image(image: yepGramBadge, tintColor: nil)\n'
            '                    emojiExpandedStatusContent = .image(image: yepGramBadge, tintColor: nil)\n'
            '                } else {\n'
            '                    emojiRegularStatusContent = .none\n'
            '                    emojiExpandedStatusContent = .none\n'
            '                }\n') + text[at + len(default):]
        write(root, path, text)
        print('patched', path, '(developer badge)')


def whats_new(root):
    path = 'submodules/TelegramUI/Sources/ApplicationContext.swift'
    anchor = '        self.notificationMessagesDisposable.set((context.account.stateManager.notificationMessages\n'
    replace(root, path, anchor,
        '        // YepGram: what\'s new, once per release.\n'
        '        let yepGramWhatsNewContext = context\n'
        '        Queue.mainQueue().after(2.0, { [weak mainWindow] in\n'
        '            let presentationData = yepGramWhatsNewContext.sharedContext.currentPresentationData.with { $0 }\n'
        '            guard let mainWindow, let whatsNew = YepGramSettings.whatsNew(lang: presentationData.strings.baseLanguageCode) else {\n'
        '                return\n'
        '            }\n'
        '            YepGramSettings.markWhatsNewSeen()\n'
        '            mainWindow.present(textAlertController(context: yepGramWhatsNewContext, title: whatsNew.title, text: whatsNew.text, actions: [TextAlertAction(type: .defaultAction, title: presentationData.strings.Common_OK, action: {})]), on: .root)\n'
        '        })\n'
        '        \n' + anchor)


def presence_account_id(root):
    # Ghost "hide online" is per account, so the presence manager has to know which account it serves.
    path = 'submodules/TelegramCore/Sources/State/ManagedAccountPresence.swift'
    replace(root, path, '    private var wasOnline: Bool = false\n', '    private var wasOnline: Bool = false\n    private let accountPeerId: PeerId\n')
    replace(root, path,
        '    init(queue: Queue, shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network) {\n        self.queue = queue\n        self.network = network\n',
        '    init(queue: Queue, shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network, accountPeerId: PeerId) {\n        self.queue = queue\n        self.network = network\n        self.accountPeerId = accountPeerId\n')
    replace(root, path,
        '    init(shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network) {\n        let queue = self.queue\n        self.impl = QueueLocalObject(queue: self.queue, generate: {\n            return AccountPresenceManagerImpl(queue: queue, shouldKeepOnlinePresence: shouldKeepOnlinePresence, network: network)\n',
        '    init(shouldKeepOnlinePresence: Signal<Bool, NoError>, network: Network, accountPeerId: PeerId) {\n        let queue = self.queue\n        self.impl = QueueLocalObject(queue: self.queue, generate: {\n            return AccountPresenceManagerImpl(queue: queue, shouldKeepOnlinePresence: shouldKeepOnlinePresence, network: network, accountPeerId: accountPeerId)\n')
    replace(root, 'submodules/TelegramCore/Sources/Account/Account.swift',
        'AccountPresenceManager(shouldKeepOnlinePresence: self.shouldKeepOnlinePresence.get(), network: network)',
        'AccountPresenceManager(shouldKeepOnlinePresence: self.shouldKeepOnlinePresence.get(), network: network, accountPeerId: peerId)')


def accounts_screen(root):
    path = 'Swiftgram/SGSettingsUI/Sources/SGSettingsController.swift'
    replace(root, path, '    case yepAccount\n    case trending\n', '    case yepAccount\n    case yepAccountList\n    case yepBackground\n    case trending\n')
    replace(root, path, '    case yepKeepEditHistory\n    case yepGhostReadAfterAction\n}', '    case yepKeepEditHistory\n    case yepGhostReadAfterAction\n    case yepBackgroundMode\n    case yepQuickAccountSwipe\n}')

    # Categories: Accounts lists the accounts; each opens its own screen (notifications and ghost mode).
    replace(root, path, '    case other\n\n    func title(_ lang: String) -> String {\n', '    case other\n    case accountDetails\n\n    func title(_ lang: String) -> String {\n')
    replace(root, path, '        case .other:\n            return yepGramText(lang, "Другое", "Other")\n        }\n',
        '        case .other:\n            return yepGramText(lang, "Другое", "Other")\n        case .accountDetails:\n            return yepGramText(lang, "Аккаунт", "Account")\n        }\n')
    replace(root, path, '        case .yepGram:\n            return [.yepGhost, .yepDeleted]\n        case .accounts:\n            return [.yepAccount]\n',
        '        case .yepGram:\n            return [.yepGhost, .yepDeleted, .yepBackground]\n        case .accounts:\n            return [.yepAccountList]\n')
    replace(root, path, '        case .other:\n            return [.content, .other]\n        }\n',
        '        case .other:\n            return [.content, .other]\n        case .accountDetails:\n            return [.yepAccount, .yepGhost]\n        }\n')
    replace(root, path, '        case .other:\n            return .yepCategoryOther\n        }\n',
        '        case .other:\n            return .yepCategoryOther\n        case .accountDetails:\n            return .yepCategoryAccounts\n        }\n')
    replace(root, path, '    for category in YepGramSettingsCategory.allCases {\n',
        '    for category in YepGramSettingsCategory.allCases {\n        if category == .accountDetails {\n            continue\n        }\n')

    replace(root, path, 'state: SGSettingsControllerState, category: YepGramSettingsCategory?, accountId: Int64) -> [SGControllerEntry] {\n',
        'state: SGSettingsControllerState, category: YepGramSettingsCategory?, accountId: Int64, accounts: [(Int64, String)]) -> [SGControllerEntry] {\n')

    replace(root, path,
        '    entries.append(.header(id: id.count, section: .yepAccount, text: yepGramText(lang, "ЭТОТ АККАУНТ", "THIS ACCOUNT"), badge: nil))\n',
        '    entries.append(.header(id: id.count, section: .yepAccountList, text: yepGramText(lang, "АККАУНТЫ", "ACCOUNTS"), badge: nil))\n'
        '    for (listedAccountId, listedAccountName) in accounts {\n'
        '        let yepGramTag = YepGramSettings.accountLabel(accountId: listedAccountId)\n'
        '        let yepGramDisplayName = yepGramTag.isEmpty ? (listedAccountName.isEmpty ? "ID \\(listedAccountId)" : listedAccountName) : "[\\(yepGramTag)] \\(listedAccountName)"\n'
        '        entries.append(.action(id: id.count, section: .yepAccountList, actionType: AnyHashable(listedAccountId), text: yepGramDisplayName, kind: .generic))\n'
        '    }\n'
        '    entries.append(.notice(id: id.count, section: .yepAccountList, text: yepGramText(lang, "Нажмите на аккаунт, чтобы настроить для него метку, уведомления и режим призрака.", "Tap an account to set up its tag, notifications and ghost mode.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepAccountList, text: yepGramText(lang, "БЫСТРЫЕ ЖЕСТЫ", "QUICK GESTURES"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepAccountList, settingName: .yepQuickAccountSwipe, value: YepGramSettings.quickAccountSwipe, text: yepGramText(lang, "Свайп по панели для смены аккаунта", "Swipe tab bar to switch account"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepAccountList, text: yepGramText(lang, "Свайп влево или вправо по нижней панели вкладок переключает между аккаунтами.", "Swipe left or right along the bottom tab bar to switch between accounts.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepAccount, text: yepGramText(lang, "МЕТКА АККАУНТА", "ACCOUNT TAG"), badge: nil))\n'
        '    let yepGramCurrentTag = YepGramSettings.accountLabel(accountId: accountId)\n'
        '    let yepGramTagActionText = yepGramCurrentTag.isEmpty ? yepGramText(lang, "Задать метку (например: Работа, Проект)", "Set tag (e.g. Work, Project)") : "[\\(yepGramCurrentTag)] " + yepGramText(lang, "Изменить метку", "Change tag")\n'
        '    entries.append(.action(id: id.count, section: .yepAccount, actionType: AnyHashable("yepEditAccountLabel"), text: yepGramTagActionText, kind: .generic))\n'
        '    entries.append(.notice(id: id.count, section: .yepAccount, text: yepGramText(lang, "Метка отображается в заголовке чатов и меню аккаунтов, чтобы вы всегда знали, с какого аккаунта пишете.", "The tag appears in the chat list title and account switcher so you always know which account is active.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepAccount, text: yepGramText(lang, "УВЕДОМЛЕНИЯ", "NOTIFICATIONS"), badge: nil))\n')
    replace(root, path,
        '"Баннеры о новых сообщениях, пока YepGram открыт. У каждого аккаунта настройка своя: чтобы поменять её для другого, переключитесь на него.", "Banners for new messages while YepGram is open. Each account has its own setting: switch to another account to change it there."',
        '"Баннеры о новых сообщениях, пока YepGram открыт или работает в фоне.", "Banners for new messages while YepGram is open or running in the background."')
    replace(root, path, 'section: .yepAccount, settingName: .hidePhoneInSettings,', 'section: .yepAccountList, settingName: .hidePhoneInSettings,')
    replace(root, path, 'entries.append(.notice(id: id.count, section: .yepAccount, text: i18n("Settings.HidePhoneInSettingsUI.Notice", lang)))',
        'entries.append(.notice(id: id.count, section: .yepAccountList, text: i18n("Settings.HidePhoneInSettingsUI.Notice", lang)))')
    replace(root, path, 'section: .yepAccount, settingName: .hideAccountInNotifications,', 'section: .yepAccountList, settingName: .hideAccountInNotifications,')

    # Background mode switch in the YepGram category.
    edit_notice = '    entries.append(.notice(id: id.count, section: .yepDeleted, text: yepGramText(lang, "Прошлые версии изменённых сообщений: удержите сообщение и выберите «История изменений».", "Earlier versions of edited messages: long-press a message and choose Edit history.")))\n'
    replace(root, path, edit_notice, edit_notice +
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepBackground, text: yepGramText(lang, "РАБОТА В ФОНЕ", "BACKGROUND"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepBackground, settingName: .yepBackgroundMode, value: YepGramSettings.backgroundMode, text: yepGramText(lang, "Работать в фоне", "Run in background"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepBackground, text: yepGramText(lang, "YepGram остаётся на связи после сворачивания: сам показывает уведомления о новых сообщениях и сохраняет удалённые сразу. Расходует больше батареи. Не работает, если смахнуть приложение из списка запущенных.", "YepGram stays connected after you leave it: it shows notifications for new messages itself and catches deleted messages right away. Uses more battery. Stops if you swipe the app away.")))\n')
    toggle = ('        case .yepGhostReadAfterAction:\n'
              '            YepGramSettings.setGhost(.readAfterAction, accountId: yepGramTargetAccountId, value)\n'
              '            simplePromise.set(true)\n')
    replace(root, path, toggle, toggle +
        '        case .yepBackgroundMode:\n'
        '            YepGramSettings.backgroundMode = value\n'
        '            if value {\n'
        '                UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound, .carPlay]) { _, _ in }\n'
        '            }\n'
        '            simplePromise.set(true)\n'
        '        case .yepQuickAccountSwipe:\n'
        '            YepGramSettings.quickAccountSwipe = value\n'
        '            simplePromise.set(true)\n')
    replace(root, path,
        '            YepGramSettings.setInAppNotificationsMuted(!value, accountId: context.account.peerId.id._internalGetInt64Value())\n',
        '            YepGramSettings.setInAppNotificationsMuted(!value, accountId: yepGramTargetAccountId)\n')

    # The controller: which account it is about, the account list, and opening an account.
    replace(root, path,
        'private func yepGramSettingsController(context: AccountContext, category: YepGramSettingsCategory?) -> ViewController {\n',
        'private func yepGramSettingsController(context: AccountContext, category: YepGramSettingsCategory?, detailsAccount: (id: Int64, name: String)? = nil) -> ViewController {\n'
        '    // Ghost and notification switches act on the account this screen is about: the opened one, else the current one.\n'
        '    let yepGramTargetAccountId = detailsAccount?.id ?? context.account.peerId.id._internalGetInt64Value()\n'
        '    let yepGramAccountNames = Atomic<[Int64: String]>(value: [:])\n')
    replace(root, path, '    }, searchInput: { searchQuery in\n',
        '    }, action: { actionType in\n'
        '        if let str = actionType.base as? String, str == "yepEditAccountLabel" {\n'
        '            let isRussian = presentationData.strings.baseLanguageCode == "ru"\n'
        '            let alert = UIAlertController(title: isRussian ? "Метка аккаунта" : "Account Tag", message: isRussian ? "Введите метку для этого аккаунта (например: Работа, Проект, Саппорт):" : "Enter a label for this account (e.g. Work, Project, Support):", preferredStyle: .alert)\n'
        '            alert.addTextField { tf in\n'
        '                tf.text = YepGramSettings.accountLabel(accountId: yepGramTargetAccountId)\n'
        '                tf.placeholder = isRussian ? "Метка" : "Label"\n'
        '            }\n'
        '            alert.addAction(UIAlertAction(title: presentationData.strings.Common_Cancel, style: .cancel, handler: nil))\n'
        '            alert.addAction(UIAlertAction(title: presentationData.strings.Common_OK, style: .default, handler: { _ in\n'
        '                let newTag = alert.textFields?.first?.text ?? ""\n'
        '                YepGramSettings.setAccountLabel(accountId: yepGramTargetAccountId, newTag)\n'
        '                simplePromise.set(true)\n'
        '            }))\n'
        '            context.sharedContext.mainWindow?.viewController?.present(alert, animated: true, completion: nil)\n'
        '            return\n'
        '        }\n'
        '        guard let listedAccountId = actionType.base as? Int64 else {\n'
        '            return\n'
        '        }\n'
        '        let name = yepGramAccountNames.with { $0[listedAccountId] } ?? ""\n'
        '        pushControllerImpl?(yepGramSettingsController(context: context, category: .accountDetails, detailsAccount: (listedAccountId, name)))\n'
        '    }, searchInput: { searchQuery in\n')
    replace(root, path, '    let signal = combineLatest(simplePromise.get(), /*sliderPromise.get(),*/ statePromise.get(),',
        '    let yepGramAccounts: Signal<[(Int64, String)], NoError> = context.sharedContext.activeAccountContexts\n'
        '    |> mapToSignal { activeAccounts -> Signal<[(Int64, String)], NoError> in\n'
        '        return combineLatest(activeAccounts.accounts.map { _, accountContext, _ -> Signal<(Int64, String), NoError> in\n'
        '            let accountId = accountContext.account.peerId.id._internalGetInt64Value()\n'
        '            return accountContext.engine.data.get(TelegramEngine.EngineData.Item.Peer.Peer(id: accountContext.account.peerId))\n'
        '            |> map { peer -> (Int64, String) in\n'
        '                guard case let .user(user)? = peer else {\n'
        '                    return (accountId, "")\n'
        '                }\n'
        '                return (accountId, [user.firstName, user.lastName].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " "))\n'
        '            }\n'
        '        })\n'
        '    }\n'
        '    \n'
        '    let signal = combineLatest(combineLatest(simplePromise.get(), yepGramAccounts), /*sliderPromise.get(),*/ statePromise.get(),')
    replace(root, path, '    |> map { _, /*sliderValue,*/ state, presentationData,', '    |> map { simpleAndAccounts, /*sliderValue,*/ state, presentationData,')
    replace(root, path,
        'state: state, category: category, accountId: context.account.peerId.id._internalGetInt64Value())\n',
        'state: state, category: category, accountId: yepGramTargetAccountId, accounts: simpleAndAccounts.1)\n')
    replace(root, path, '        let entries = SGControllerEntries(',
        '        let _ = yepGramAccountNames.swap(Dictionary(simpleAndAccounts.1, uniquingKeysWith: { first, _ in first }))\n'
        '        let entries = SGControllerEntries(')
    replace(root, path, 'title: .text(category?.title(presentationData.strings.baseLanguageCode) ?? "YepGram")',
        'title: .text(detailsAccount?.name ?? category?.title(presentationData.strings.baseLanguageCode) ?? "YepGram")')


def background_mode(root):
    # Keepalive: silent WAV loop through AVAudioPlayer actively feeds CoreAudio so iOS keeps the app awake.
    path = 'submodules/TelegramUI/Sources/SharedWakeupManager.swift'
    replace(root, path, 'import TelegramPresentationData\n', 'import TelegramPresentationData\nimport SGSimpleSettings\n')
    replace(root, path,
        '    private var silenceAudioRenderer: MediaPlayerAudioRenderer?\n',
        '    private var silenceAudioRenderer: MediaPlayerAudioRenderer?\n    private var yepGramSilencePlayer: AVAudioPlayer?\n')
    call = '        self.updateAccounts(hasTasks: hasTasksForBackgroundExtension, endTaskAfterTransactionsComplete: endTaskAfterTransactionsComplete)\n'
    replace(root, path, call,
        '        // YepGram background mode: play silence while in the background so the app keeps running and connected.\n'
        '        // An infinite silent WAV loop through AVAudioPlayer actively feeds CoreAudio so iOS never suspends the process.\n'
        '        // It yields to the app\'s own audio (voice messages, calls) and resumes when that ends.\n'
        '        if !self.inForeground && !self.hasActiveAudioSession && YepGramSettings.backgroundMode {\n'
        '            if self.yepGramSilencePlayer == nil {\n'
        '                let audioSession = AVAudioSession.sharedInstance()\n'
        '                let _ = try? audioSession.setCategory(.playback, mode: .default, options: [.mixWithOthers])\n'
        '                let _ = try? audioSession.setActive(true)\n'
        '                if let player = try? AVAudioPlayer(data: makeYepGramSilentWav()) {\n'
        '                    player.numberOfLoops = -1\n'
        '                    player.volume = 0.01\n'
        '                    player.prepareToPlay()\n'
        '                    player.play()\n'
        '                    self.yepGramSilencePlayer = player\n'
        '                }\n'
        '            }\n'
        '        } else if let player = self.yepGramSilencePlayer {\n'
        '            self.yepGramSilencePlayer = nil\n'
        '            player.stop()\n'
        '            let _ = try? AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])\n'
        '        }\n'
        '        \n' + call)
    # While it runs, every account keeps receiving updates.
    replace(root, path,
        '|| self.silenceAudioRenderer != nil {\n',
        '|| self.silenceAudioRenderer != nil || self.yepGramSilencePlayer != nil {\n')
    replace(root, path,
        '                if (self.inForeground && primary) || !tasks.isEmpty || (self.activeExplicitExtensionTimer != nil && primary) {\n',
        '                if (self.inForeground && primary) || !tasks.isEmpty || (self.activeExplicitExtensionTimer != nil && primary) || self.yepGramSilencePlayer != nil {\n')
    replace(root, path,
        '                account.shouldExplicitelyKeepWorkerConnections.set(.single(tasks.backgroundAudio || tasks.backgroundLocation || tasks.importantTasks.pendingStoryCount != 0 || tasks.importantTasks.pendingMessageCount != 0))\n',
        '                account.shouldExplicitelyKeepWorkerConnections.set(.single(tasks.backgroundAudio || tasks.backgroundLocation || tasks.importantTasks.pendingStoryCount != 0 || tasks.importantTasks.pendingMessageCount != 0 || self.yepGramSilencePlayer != nil))\n')
    text = read(root, path)
    write(root, path, text.rstrip('\n') + '\n\n'
        '// Minimal 1-second RIFF PCM WAV buffer (8000Hz, 16-bit mono) of digital silence.\n'
        'private func makeYepGramSilentWav() -> Data {\n'
        '    let header: [UInt8] = [\n'
        '        0x52, 0x49, 0x46, 0x46,\n'
        '        0xA4, 0x3E, 0x00, 0x00,\n'
        '        0x57, 0x41, 0x56, 0x45,\n'
        '        0x66, 0x6D, 0x74, 0x20,\n'
        '        0x10, 0x00, 0x00, 0x00,\n'
        '        0x01, 0x00,\n'
        '        0x01, 0x00,\n'
        '        0x40, 0x1F, 0x00, 0x00,\n'
        '        0x80, 0x3E, 0x00, 0x00,\n'
        '        0x02, 0x00,\n'
        '        0x10, 0x00,\n'
        '        0x64, 0x61, 0x74, 0x61,\n'
        '        0x80, 0x3E, 0x00, 0x00\n'
        '    ]\n'
        '    var data = Data(header)\n'
        '    data.append(Data(count: 16000))\n'
        '    return data\n'
        '}\n')

    # Notification permission & presentation in AppDelegate
    path = 'submodules/TelegramUI/Sources/AppDelegate.swift'
    replace(root, path,
        '                    var authorizeNotifications = true\n                    if #available(iOS 10.0, *) {\n                        authorizeNotifications = false\n                    }\n                    self.registerForNotifications(context: context.context, authorize: authorizeNotifications)\n',
        '                    // YepGram: unconditionally request notification authorization so local notifications work on sideloaded builds.\n                    let authorizeNotifications = true\n                    self.registerForNotifications(context: context.context, authorize: authorizeNotifications)\n')
    replace(root, path,
        '    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {\n',
        '    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {\n'
        '        if notification.request.identifier.hasPrefix("yepgram-") {\n'
        '            if #available(iOS 14.0, *) {\n'
        '                completionHandler([.banner, .sound, .badge, .list])\n'
        '            } else {\n'
        '                completionHandler([.sound, .badge])\n'
        '            }\n'
        '            return\n'
        '        }\n')

    # New messages while in the background become rich local notifications.
    path = 'submodules/TelegramUI/Sources/ApplicationContext.swift'
    replace(root, path, 'import SGSimpleSettings\n', 'import SGSimpleSettings\nimport UserNotifications\n')
    anchor = '            if let strongSelf = self, let (messages, _, notify, threadData) = messageList.last, let firstMessage = messages.first {\n'
    replace(root, path, anchor, anchor +
        '                // YepGram background mode: no pushes on a sideloaded build, so notify locally.\n'
        '                if UIApplication.shared.applicationState != .active && YepGramSettings.backgroundMode && notify {\n'
        '                    yepGramPostLocalNotification(message: firstMessage, count: messages.count, accountId: strongSelf.context.account.id.rawValue)\n'
        '                    return\n'
        '                }\n')
    text = read(root, path)
    write(root, path, text.rstrip('\n') + '\n\n'
        '// YepGram background mode: a rich local notification for a new message.\n'
        'func yepGramPostLocalNotification(message: EngineRawMessage, count: Int, accountId: Int64? = nil) {\n'
        '    let content = UNMutableNotificationContent()\n'
        '    let chatPeer = message.peers[message.id.peerId]\n'
        '    let authorPeer = message.author\n'
        '    let chatTitle = chatPeer?.debugDisplayTitle ?? ""\n'
        '    let authorTitle = authorPeer?.debugDisplayTitle ?? ""\n'
        '    let isUserChat = chatPeer is TelegramUser\n'
        '    if isUserChat {\n'
        '        let name = !authorTitle.isEmpty ? authorTitle : chatTitle\n'
        '        content.title = !name.isEmpty ? name : "Сообщение"\n'
        '    } else {\n'
        '        if !chatTitle.isEmpty {\n'
        '            if !authorTitle.isEmpty && authorTitle != chatTitle {\n'
        '                content.title = "\\(chatTitle): \\(authorTitle)"\n'
        '            } else {\n'
        '                content.title = chatTitle\n'
        '            }\n'
        '        } else {\n'
        '            content.title = !authorTitle.isEmpty ? authorTitle : "Сообщение"\n'
        '        }\n'
        '    }\n'
        '    var body = message.text\n'
        '    if body.isEmpty {\n'
        '        for media in message.media {\n'
        '            if media is TelegramMediaImage {\n'
        '                body = "📷 Фото"\n'
        '                break\n'
        '            } else if let file = media as? TelegramMediaFile {\n'
        '                if file.isVoice {\n'
        '                    body = "🎤 Голосовое сообщение"\n'
        '                } else if file.isInstantVideo {\n'
        '                    body = "📹 Видеосообщение"\n'
        '                } else if file.isVideo {\n'
        '                    body = "📹 Видео"\n'
        '                } else if file.isSticker {\n'
        '                    body = "Стикер"\n'
        '                } else if file.isAnimated {\n'
        '                    body = "GIF"\n'
        '                } else {\n'
        '                    body = "📎 " + (file.fileName ?? "Файл")\n'
        '                }\n'
        '                break\n'
        '            } else if media is TelegramMediaContact {\n'
        '                body = "👤 Контакт"\n'
        '                break\n'
        '            } else if media is TelegramMediaMap {\n'
        '                body = "📍 Геолокация"\n'
        '                break\n'
        '            } else if media is TelegramMediaPoll {\n'
        '                body = "📊 Опрос"\n'
        '                break\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '    if body.isEmpty {\n'
        '        body = "Сообщение"\n'
        '    }\n'
        '    if count > 1 {\n'
        '        body += " (+\\(count - 1))"\n'
        '    }\n'
        '    content.body = body\n'
        '    content.sound = .default\n'
        '    content.categoryIdentifier = "c"\n'
        '    content.threadIdentifier = "\\(message.id.peerId.toInt64())"\n'
        '    var userInfo: [AnyHashable: Any] = [\n'
        '        "peerId": message.id.peerId.toInt64(),\n'
        '        "messageId.namespace": message.id.namespace,\n'
        '        "messageId.id": message.id.id\n'
        '    ]\n'
        '    if let accountId = accountId {\n'
        '        userInfo["accountId"] = accountId\n'
        '    }\n'
        '    content.userInfo = userInfo\n'
        '    let request = UNNotificationRequest(identifier: "yepgram-\\(message.id.peerId.toInt64())-\\(message.id.id)", content: content, trigger: nil)\n'
        '    UNUserNotificationCenter.current().add(request, withCompletionHandler: nil)\n'
        '}\n')
    print('patched', path, '(local notifications)')

def background_all_accounts(root):
    # The primary account is notified by its ApplicationContext; the others are watched here.
    path = 'submodules/TelegramUI/Sources/SharedAccountContext.swift'
    replace(root, path,
        '    private var immediateSGStatusValue = Atomic<SGStatus>(value: SGStatus.default)\n',
        '    private var immediateSGStatusValue = Atomic<SGStatus>(value: SGStatus.default)\n'
        '    private let yepGramBackgroundNotificationsDisposable = MetaDisposable()\n')
    replace(root, path,
        '        // MARK: Swiftgram\n        let immediateSGStatusValue = self.immediateSGStatusValue\n',
        '        // YepGram background mode: local notifications for every account but the primary one.\n'
        '        self.yepGramBackgroundNotificationsDisposable.set((self.activeAccountContexts\n'
        '        |> mapToSignal { activeAccounts -> Signal<[(EngineRawMessage, Int, Int64)], NoError> in\n'
        '            let primaryId = activeAccounts.primary?.account.id\n'
        '            let others = activeAccounts.accounts.map { $0.1 }.filter { $0.account.id != primaryId }\n'
        '            return Signal { subscriber in\n'
        '                let disposables = DisposableSet()\n'
        '                for accountContext in others {\n'
        '                    let accountRecordId = accountContext.account.id.rawValue\n'
        '                    let peerIdValue = accountContext.account.peerId.id._internalGetInt64Value()\n'
        '                    disposables.add(accountContext.account.stateManager.notificationMessages.start(next: { list in\n'
        '                        if YepGramSettings.isInAppNotificationsMuted(accountId: peerIdValue) {\n'
        '                            return\n'
        '                        }\n'
        '                        let items = list.compactMap { item -> (EngineRawMessage, Int, Int64)? in\n'
        '                            guard item.2, let first = item.0.first else {\n'
        '                                return nil\n'
        '                            }\n'
        '                            return (first, item.0.count, accountRecordId)\n'
        '                        }\n'
        '                        if !items.isEmpty {\n'
        '                            subscriber.putNext(items)\n'
        '                        }\n'
        '                    }))\n'
        '                }\n'
        '                return disposables\n'
        '            }\n'
        '        }\n'
        '        |> deliverOnMainQueue).start(next: { items in\n'
        '            guard UIApplication.shared.applicationState != .active, YepGramSettings.backgroundMode else {\n'
        '                return\n'
        '            }\n'
        '            for (message, count, accountId) in items {\n'
        '                yepGramPostLocalNotification(message: message, count: count, accountId: accountId)\n'
        '            }\n'
        '        }))\n'
        '        \n'
        '        // MARK: Swiftgram\n        let immediateSGStatusValue = self.immediateSGStatusValue\n')


def account_limits(root):
    # Raise safety threshold from 6 to 500 accounts so new accounts are added without warning dialogs.
    path = 'submodules/AccountUtils/Sources/AccountUtils.swift'
    replace(root, path,
        'public let maximumSafeNumberOfAccounts = 6\n',
        'public let maximumSafeNumberOfAccounts = 500\n')


def account_labels_in_switcher(root):
    # Display the account tag/label in the account switcher popup menu.
    path = 'submodules/TelegramUI/Components/PeerInfo/AccountPeerContextItem/Sources/AccountPeerContextItem.swift'
    replace(root, path,
        '        let peerTitle = item.peer.displayTitle(strings: presentationData.strings, displayOrder: presentationData.nameDisplayOrder)\n',
        '        let rawPeerTitle = item.peer.displayTitle(strings: presentationData.strings, displayOrder: presentationData.nameDisplayOrder)\n'
        '        let accountTag = UserDefaults.standard.string(forKey: "yepgram.accountLabel.\\(item.account.peerId.id._internalGetInt64Value())") ?? ""\n'
        '        let peerTitle = accountTag.isEmpty ? rawPeerTitle : "[\\(accountTag)] \\(rawPeerTitle)"\n')


def quick_account_swipe(root):
    path = 'submodules/TelegramUI/Sources/TelegramRootController.swift'
    replace(root, path,
        '    private let context: AccountContext\n',
        '    fileprivate let context: AccountContext\n    private var yepGramSwipeHandler: AnyObject?\n')

    setup_anchor = '        self.rootTabController = tabBarController\n        self.pushViewController(tabBarController, animated: false)\n'
    replace(root, path, setup_anchor, setup_anchor +
        '        \n'
        '        // YepGram: swipe along the bottom tab bar to quickly switch accounts.\n'
        '        let swipeHandler = YepGramTabBarSwipeHandler(rootController: self)\n'
        '        swipeHandler.setup(tabBarController: tabBarController)\n'
        '        self.yepGramSwipeHandler = swipeHandler\n')

    text = read(root, path)
    write(root, path, text.rstrip('\n') + '\n\n' +
        '// YepGram: quick account switching via swipe on the bottom tab bar.\n'
        'private final class YepGramTabBarSwipeHandler: NSObject, UIGestureRecognizerDelegate {\n'
        '    private weak var rootController: TelegramRootController?\n'
        '    \n'
        '    init(rootController: TelegramRootController) {\n'
        '        self.rootController = rootController\n'
        '        super.init()\n'
        '    }\n'
        '    \n'
        '    func setup(tabBarController: TabBarControllerImpl) {\n'
        '        let left = UISwipeGestureRecognizer(target: self, action: #selector(self.handleSwipe(_:)))\n'
        '        left.direction = .left\n'
        '        left.delegate = self\n'
        '        tabBarController.view.addGestureRecognizer(left)\n'
        '        \n'
        '        let right = UISwipeGestureRecognizer(target: self, action: #selector(self.handleSwipe(_:)))\n'
        '        right.direction = .right\n'
        '        right.delegate = self\n'
        '        tabBarController.view.addGestureRecognizer(right)\n'
        '    }\n'
        '    \n'
        '    @objc private func handleSwipe(_ gesture: UISwipeGestureRecognizer) {\n'
        '        guard YepGramSettings.quickAccountSwipe, let root = self.rootController else { return }\n'
        '        let isLeft = gesture.direction == .left\n'
        '        let sharedContext = root.context.sharedContext\n'
        '        let _ = (sharedContext.activeAccountContexts\n'
        '        |> take(1)\n'
        '        |> deliverOnMainQueue).startStandalone(next: { activeAccounts in\n'
        '            let accounts = activeAccounts.accounts\n'
        '            guard accounts.count > 1, let currentId = activeAccounts.primary?.account.id else {\n'
        '                return\n'
        '            }\n'
        '            guard let currentIndex = accounts.firstIndex(where: { $0.0 == currentId }) else {\n'
        '                return\n'
        '            }\n'
        '            let targetIndex = isLeft ? (currentIndex + 1) % accounts.count : (currentIndex - 1 + accounts.count) % accounts.count\n'
        '            let targetId = accounts[targetIndex].0\n'
        '            let generator = UIImpactFeedbackGenerator(style: .medium)\n'
        '            generator.impactOccurred()\n'
        '            sharedContext.switchToAccount(id: targetId)\n'
        '        })\n'
        '    }\n'
        '    \n'
        '    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {\n'
        '        guard YepGramSettings.quickAccountSwipe else { return false }\n'
        '        guard let view = gestureRecognizer.view else { return false }\n'
        '        let location = touch.location(in: view)\n'
        '        return location.y >= view.bounds.height - 70.0\n'
        '    }\n'
        '}\n')
    print('patched', path, '(quick account swipe)')


def fast_build_optimizations(root):
    # Disable redundant dSYM generation in release_arm64 for sideload builds (saves ~3-5 minutes of CPU & disk I/O).
    path = 'build-system/Make/Make.py'
    replace(root, path,
        "                # Generate DSYM files when building.\n"
        "                '--apple_generate_dsym',\n\n"
        "                # Require DSYM files as build output.\n"
        "                '--output_groups=+dsyms',\n",
        "")
    replace(root, path,
        "        for dsym_path in dsym_paths:\n"
        "            file_name = os.path.basename(dsym_path)\n"
        "            shutil.copytree(dsym_path, artifacts_path + '/DSYMs/{}'.format(file_name))\n"
        "        previous_directory = os.getcwd()\n"
        "        os.chdir(artifacts_path)\n"
        "        run_executable_with_output('zip', arguments=[\n"
        "            '-r',\n"
        "            'Swiftgram.DSYMs.zip',\n"
        "            './DSYMs'\n"
        "        ], check_result=True)\n"
        "        os.chdir(previous_directory)\n"
        "        shutil.rmtree(artifacts_path + '/DSYMs')\n",
        "        if len(dsym_paths) > 0:\n"
        "            for dsym_path in dsym_paths:\n"
        "                file_name = os.path.basename(dsym_path)\n"
        "                shutil.copytree(dsym_path, artifacts_path + '/DSYMs/{}'.format(file_name))\n"
        "            previous_directory = os.getcwd()\n"
        "            os.chdir(artifacts_path)\n"
        "            run_executable_with_output('zip', arguments=[\n"
        "                '-r',\n"
        "                'Swiftgram.DSYMs.zip',\n"
        "                './DSYMs'\n"
        "            ], check_result=True)\n"
        "            os.chdir(previous_directory)\n"
        "        if os.path.exists(artifacts_path + '/DSYMs'):\n"
        "            shutil.rmtree(artifacts_path + '/DSYMs')\n")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    rename_app(root)
    replace_icon(root)
    grey_theme(root)
    keep_deleted_messages(root)
    deleted_mark_in_chat(root)
    sideload_app_group(root)
    rebrand_texts(root)
    branded_icons(root)
    remove_swiftgram_pro(root)
    ghost_mode(root)
    yepgram_settings_ui(root)
    unlock_swiftgram_pro_features(root)
    per_account_in_app_notifications(root)
    intro_logo(root)
    edit_history(root)
    ghost_extras(root)
    message_ids_in_menu(root)
    developer_badge(root)
    whats_new(root)
    presence_account_id(root)
    accounts_screen(root)
    background_mode(root)
    background_all_accounts(root)
    account_limits(root)
    account_labels_in_switcher(root)
    quick_account_swipe(root)
    fast_build_optimizations(root)
    if failures:
        print('\nYepGram patch FAILED:')
        for failure in failures:
            print(' -', failure)
        sys.exit(1)
    print('\nYepGram patch applied.')


if __name__ == '__main__':
    main()
