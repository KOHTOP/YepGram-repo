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


def lime_theme(root):
    path = 'submodules/TelegramUIPreferences/Sources/PresentationThemeSettings.swift'
    replace(root, path,
        'public enum PresentationThemeBaseColor: Int32, CaseIterable {',
        '''// YepGram palette.
public let yepGramNightAccentColor: UInt32 = 0xa4e04a
public let yepGramNightOutgoingBubbleColor: UInt32 = 0x3a4430
public let yepGramDayAccentColor: UInt32 = 0x5fae1e
public let yepGramDayOutgoingBubbleColor: UInt32 = 0xe4f6cc

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
        '            // YepGram: a message the server deleted shows a trash icon where the pin would be.\n'
        '            if arguments.isDeleted && arguments.replyCount == 0 {\n'
        '                repliesImage = yepGramDeletedIcon(color: dateColor, size: graphics.incomingDateAndStatusPinnedIcon.size)\n'
        '            }' + blank + '            var updatedDateText = arguments.dateText\n')
    replace(root, path,
        '            } else if arguments.isPinned {\n                reactionInset += 12.0',
        '            } else if arguments.isPinned || arguments.isDeleted {\n                reactionInset += 12.0')
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
    if failures:
        print('\nYepGram patch FAILED:')
        for failure in failures:
            print(' -', failure)
        sys.exit(1)
    print('\nYepGram patch applied.')


if __name__ == '__main__':
    main()
