import Foundation

// YepGram's own switches. Each one is read on the path it guards, so a change applies at once.
public enum YepGramSettings {
    private enum Key: String {
        case ghostNoReadReceipts = "yepgram.ghost.noReadReceipts"
        case ghostHideOnline = "yepgram.ghost.hideOnline"
        case ghostNoTyping = "yepgram.ghost.noTyping"
        case keepDeletedMessages = "yepgram.keepDeletedMessages"
    }

    private static func read(_ key: Key, default defaultValue: Bool) -> Bool {
        return UserDefaults.standard.object(forKey: key.rawValue) as? Bool ?? defaultValue
    }

    private static func store(_ key: Key, _ value: Bool) {
        UserDefaults.standard.set(value, forKey: key.rawValue)
    }

    /// Read marks (and "listened" for voice and video messages) stay local; the server and the sender are not told.
    public static var ghostNoReadReceipts: Bool {
        get { return YepGramSettings.read(.ghostNoReadReceipts, default: false) }
        set { YepGramSettings.store(.ghostNoReadReceipts, newValue) }
    }

    /// The account always reports itself offline.
    public static var ghostHideOnline: Bool {
        get { return YepGramSettings.read(.ghostHideOnline, default: false) }
        set { YepGramSettings.store(.ghostHideOnline, newValue) }
    }

    /// No "typing…", "recording…" or similar activity is sent.
    public static var ghostNoTyping: Bool {
        get { return YepGramSettings.read(.ghostNoTyping, default: false) }
        set { YepGramSettings.store(.ghostNoTyping, newValue) }
    }

    /// Messages the server deletes stay in the chat with a deleted mark.
    public static var keepDeletedMessages: Bool {
        get { return YepGramSettings.read(.keepDeletedMessages, default: true) }
        set { YepGramSettings.store(.keepDeletedMessages, newValue) }
    }

    /// With ghost mode on, replying, reacting or voting in a chat marks it read, so the sender doesn't see
    /// an answer from someone who never read the message.
    public static var ghostReadAfterAction: Bool {
        get { return UserDefaults.standard.object(forKey: "yepgram.ghost.readAfterAction") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "yepgram.ghost.readAfterAction") }
    }

    /// Ghost mode is set per account. An account without its own value follows the app-wide one above,
    /// which is also what earlier builds stored.
    public enum GhostOption: String {
        case noReadReceipts
        case hideOnline
        case noTyping
        case readAfterAction
    }

    public static func ghost(_ option: GhostOption, accountId: Int64) -> Bool {
        if let value = UserDefaults.standard.object(forKey: "yepgram.ghost.\(accountId).\(option.rawValue)") as? Bool {
            return value
        }
        switch option {
        case .noReadReceipts:
            return YepGramSettings.ghostNoReadReceipts
        case .hideOnline:
            return YepGramSettings.ghostHideOnline
        case .noTyping:
            return YepGramSettings.ghostNoTyping
        case .readAfterAction:
            return YepGramSettings.ghostReadAfterAction
        }
    }

    public static func setGhost(_ option: GhostOption, accountId: Int64, _ value: Bool) {
        UserDefaults.standard.set(value, forKey: "yepgram.ghost.\(accountId).\(option.rawValue)")
    }

    /// Ghost mode as one switch: any of its parts counts as on.
    public static func isGhostModeOn(accountId: Int64) -> Bool {
        return YepGramSettings.ghost(.noReadReceipts, accountId: accountId) || YepGramSettings.ghost(.hideOnline, accountId: accountId) || YepGramSettings.ghost(.noTyping, accountId: accountId)
    }

    public static func setGhostMode(_ enabled: Bool, accountId: Int64) {
        YepGramSettings.setGhost(.noReadReceipts, accountId: accountId, enabled)
        YepGramSettings.setGhost(.hideOnline, accountId: accountId, enabled)
        YepGramSettings.setGhost(.noTyping, accountId: accountId, enabled)
    }

    /// Background mode: YepGram keeps its connection after it is sent to the background (by playing
    /// silence) and shows local notifications for new messages, since a sideloaded build gets no pushes.
    public static var backgroundMode: Bool {
        get { return UserDefaults.standard.object(forKey: "yepgram.backgroundMode") as? Bool ?? false }
        set { UserDefaults.standard.set(newValue, forKey: "yepgram.backgroundMode") }
    }

    /// "What's new" is shown once per release; bump the version with each release that has news.
    public static let whatsNewVersion = "2"

    public static func whatsNew(lang: String) -> (title: String, text: String)? {
        if UserDefaults.standard.string(forKey: "yepgram.whatsNewSeen") == YepGramSettings.whatsNewVersion {
            return nil
        }
        if lang == "ru" {
            return ("Что нового в YepGram", "• Настройки по категориям с поиском\n• Режим призрака: включается долгим нажатием на вкладку «Чаты», 👻 в заголовке, пока он включён\n• «Прочитать после действия»: ответ, реакция или голос отмечают чат прочитанным\n• История изменений сообщений\n• ID чата и сообщения в меню сообщения\n• Инструменты бывшего Swiftgram Pro бесплатно\n• Аккаунты: свой режим призрака и уведомления для каждого аккаунта\n• Работа в фоне: YepGram остаётся на связи после сворачивания и сам показывает уведомления")
        }
        return ("What's new in YepGram", "• Settings in categories, with search\n• Ghost mode: long-press the Chats tab to toggle it, 👻 in the title while it's on\n• Read after action: replying, reacting or voting marks the chat read\n• Message edit history\n• Chat and message IDs in the message menu\n• Former Swiftgram Pro tools, free\n• Accounts: ghost mode and notifications for each account\n• Background mode: YepGram stays connected after you leave it and shows notifications itself")
    }

    public static func markWhatsNewSeen() {
        UserDefaults.standard.set(YepGramSettings.whatsNewVersion, forKey: "yepgram.whatsNewSeen")
    }

    /// Edited messages keep their earlier texts, viewable from the message menu.
    public static var keepEditHistory: Bool {
        get { return UserDefaults.standard.object(forKey: "yepgram.keepEditHistory") as? Bool ?? true }
        set { UserDefaults.standard.set(newValue, forKey: "yepgram.keepEditHistory") }
    }

    private static let mutedInAppAccountsKey = "yepgram.mutedInAppAccounts"

    /// In-app banners for new messages, switched off for one account only.
    public static func isInAppNotificationsMuted(accountId: Int64) -> Bool {
        let ids = UserDefaults.standard.array(forKey: YepGramSettings.mutedInAppAccountsKey) as? [String] ?? []
        return ids.contains(String(accountId))
    }

    public static func setInAppNotificationsMuted(_ muted: Bool, accountId: Int64) {
        var ids = UserDefaults.standard.array(forKey: YepGramSettings.mutedInAppAccountsKey) as? [String] ?? []
        ids.removeAll(where: { $0 == String(accountId) })
        if muted {
            ids.append(String(accountId))
        }
        UserDefaults.standard.set(ids, forKey: YepGramSettings.mutedInAppAccountsKey)
    }

    public static var channelUrl: String {
        return "https://t.me/yepgramoff"
    }

    public static var sourceUrl: String {
        return "https://github.com/KOHTOP/YepGram-repo"
    }
}
