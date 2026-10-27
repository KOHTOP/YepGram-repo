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


def lime_theme(root):
    path = 'submodules/TelegramUIPreferences/Sources/PresentationThemeSettings.swift'
    replace(root, path,
        'public enum PresentationThemeBaseColor: Int32, CaseIterable {',
        '''// YepGram palette.
public let yepGramNightAccentColor: UInt32 = 0xa4e04a
public let yepGramNightOutgoingBubbleColor: UInt32 = 0x3a3a3e
public let yepGramDayAccentColor: UInt32 = 0x5fae1e
public let yepGramDayOutgoingBubbleColor: UInt32 = 0xe3e3e8

public enum PresentationThemeBaseColor: Int32, CaseIterable {''')
    replace(root, path,
        '        return PresentationThemeSettings(theme: .builtin(.dayClassic), themePreferredBaseTheme: [:], themeSpecificAccentColors: [:], themeSpecificChatWallpapers: [:],',
        '''        // YepGram: dark grey night theme with a lime accent by default; the day theme gets the same accent.
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
        'public let defaultDayAccentColor = UIColor(rgb: 0x5fae1e) // YepGram lime\n')


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
        '    if YepGramSettings.ghostNoReadReceipts {\n        return .single(readState)\n    }\n')

    header = 'private func synchronizeConsumeMessageContents(transaction: Transaction, network: Network, stateManager: AccountStateManager, peerId: PeerId, operation: SynchronizeConsumeMessageContentsOperation) -> Signal<Void, NoError> {\n'
    replace(root, state + 'ManagedSynchronizeConsumeMessageContentsOperations.swift', header,
        header + '    // YepGram ghost mode: "listened"/"watched" is a read receipt too.\n'
        '    if YepGramSettings.ghostNoReadReceipts {\n        return .complete()\n    }\n')

    replace(root, state + 'ManagedAccountPresence.swift',
        '    private func updatePresence(_ isOnline: Bool) {\n',
        '    private func updatePresence(_ requestedOnline: Bool) {\n'
        '        // YepGram ghost mode: always report offline. Read on every refresh, so toggling applies at the next one.\n'
        '        let isOnline = requestedOnline && !YepGramSettings.ghostHideOnline\n')

    header = 'private func requestActivity(postbox: Postbox, network: Network, accountPeerId: PeerId, peerId: PeerId, threadId: Int64?, activity: PeerInputActivity?) -> Signal<Void, NoError> {\n'
    replace(root, state + 'ManagedLocalInputActivities.swift', header,
        header + '    // YepGram ghost mode: no "typing…" and similar activity.\n'
        '    if YepGramSettings.ghostNoTyping {\n        return .complete()\n    }\n')


def yepgram_settings_ui(root):
    path = 'Swiftgram/SGSettingsUI/Sources/SGSettingsController.swift'
    replace(root, path, '    case search\n    case trending\n', '    case search\n    case yepGhost\n    case yepDeleted\n    case trending\n')
    replace(root, path, '    case accountColors\n    case other\n}', '    case accountColors\n    case other\n    case yepSupport\n}')
    replace(root, path, '    case hideAccountInNotifications\n}',
        '    case hideAccountInNotifications\n    case yepGhostNoReadReceipts\n    case yepGhostHideOnline\n    case yepGhostNoTyping\n    case yepKeepDeletedMessages\n}')
    replace(root, path, '    case contentSettings\n    case languageSettings\n}', '    case contentSettings\n    case languageSettings\n    case yepSupport\n}')

    replace(root, path, 'private func SGControllerEntries(',
        '// YepGram strings: Russian for a Russian interface, English otherwise.\n'
        'private func yepGramText(_ lang: String, _ ru: String, _ en: String) -> String {\n'
        '    return lang == "ru" ? ru : en\n'
        '}\n\n'
        'private func SGControllerEntries(')

    search = '    entries.append(.searchInput(id: id.count, section: .search, title: NSAttributedString(string: "🔍"), text: state.searchQuery ?? "", placeholder: strings.Common_Search))\n'
    replace(root, path, search, search +
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepGhost, text: yepGramText(lang, "РЕЖИМ ПРИЗРАКА", "GHOST MODE"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostNoReadReceipts, value: YepGramSettings.ghostNoReadReceipts, text: yepGramText(lang, "Не отправлять «прочитано»", "Don\'t send read receipts"), enabled: true))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostHideOnline, value: YepGramSettings.ghostHideOnline, text: yepGramText(lang, "Не показывать «в сети»", "Hide online status"), enabled: true))\n'
        '    entries.append(.toggle(id: id.count, section: .yepGhost, settingName: .yepGhostNoTyping, value: YepGramSettings.ghostNoTyping, text: yepGramText(lang, "Не отправлять «печатает…»", "Don\'t send typing status"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepGhost, text: yepGramText(lang, "Собеседники не увидят, что вы прочитали их сообщения, прослушали голосовые, были в сети или печатаете. Если вы сами напишете в чат, Telegram отметит его прочитанным.", "Others won\'t see that you read their messages, played voice messages, were online or are typing. Sending a message to a chat still marks it read.")))\n'
        '    \n'
        '    entries.append(.header(id: id.count, section: .yepDeleted, text: yepGramText(lang, "УДАЛЁННЫЕ СООБЩЕНИЯ", "DELETED MESSAGES"), badge: nil))\n'
        '    entries.append(.toggle(id: id.count, section: .yepDeleted, settingName: .yepKeepDeletedMessages, value: YepGramSettings.keepDeletedMessages, text: yepGramText(lang, "Сохранять удалённые сообщения", "Keep deleted messages"), enabled: true))\n'
        '    entries.append(.notice(id: id.count, section: .yepDeleted, text: yepGramText(lang, "Сообщения, которые удалил собеседник, остаются в чате полупрозрачными и с корзиной у времени.", "Messages others delete stay in the chat, faded, with a trash mark next to the time.")))\n')

    end = '    return filterSGItemListUIEntrires(entries: entries, by: state.searchQuery)\n'
    replace(root, path, end,
        '    entries.append(.header(id: id.count, section: .yepSupport, text: yepGramText(lang, "ПОДДЕРЖКА ПРОЕКТА", "SUPPORT THE PROJECT"), badge: nil))\n'
        '    entries.append(.disclosure(id: id.count, section: .yepSupport, link: .yepSupport, text: yepGramText(lang, "Поддержать YepGram", "Support YepGram")))\n'
        '    entries.append(.notice(id: id.count, section: .yepSupport, text: yepGramText(lang, "Новости, исходный код и способы помочь проекту.", "News, source code and ways to help the project.")))\n'
        '    \n' + end)

    toggles = ('        case .hideAccountInNotifications:\n'
               '            SGSimpleSettings.shared.hideAccountInNotifications = value\n'
               '            SGSimpleSettings.shared.synchronizeShared()\n')
    replace(root, path, toggles, toggles +
        '        case .yepGhostNoReadReceipts:\n'
        '            YepGramSettings.ghostNoReadReceipts = value\n'
        '            simplePromise.set(true)\n'
        '        case .yepGhostHideOnline:\n'
        '            YepGramSettings.ghostHideOnline = value\n'
        '            simplePromise.set(true)\n'
        '        case .yepGhostNoTyping:\n'
        '            YepGramSettings.ghostNoTyping = value\n'
        '            simplePromise.set(true)\n'
        '        case .yepKeepDeletedMessages:\n'
        '            YepGramSettings.keepDeletedMessages = value\n'
        '            simplePromise.set(true)\n')

    links = ('            case .languageSettings:\n'
             '                pushControllerImpl?(context.sharedContext.makeLocalizationListController(context: context))\n')
    replace(root, path, links, links +
        '            case .yepSupport:\n'
        '                context.sharedContext.applicationBindings.openUrl(YepGramSettings.supportUrl)\n')


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    root = os.path.abspath(sys.argv[1])
    rename_app(root)
    replace_icon(root)
    lime_theme(root)
    keep_deleted_messages(root)
    deleted_mark_in_chat(root)
    sideload_app_group(root)
    rebrand_texts(root)
    branded_icons(root)
    remove_swiftgram_pro(root)
    ghost_mode(root)
    yepgram_settings_ui(root)
    if failures:
        print('\nYepGram patch FAILED:')
        for failure in failures:
            print(' -', failure)
        sys.exit(1)
    print('\nYepGram patch applied.')


if __name__ == '__main__':
    main()
