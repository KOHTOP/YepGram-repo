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

    public static var supportUrl: String {
        return "https://github.com/KOHTOP/YepGram-repo"
    }
}
