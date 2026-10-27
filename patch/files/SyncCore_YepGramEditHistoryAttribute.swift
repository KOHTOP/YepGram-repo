import Foundation
import Postbox
import SGSimpleSettings

// YepGram: the earlier texts of an edited message, oldest first, each with the time it was written.
public final class YepGramEditHistoryAttribute: MessageAttribute, Equatable {
    public let texts: [String]
    public let dates: [Int32]

    public init(texts: [String], dates: [Int32]) {
        self.texts = texts
        self.dates = dates
    }

    public required init(decoder: PostboxDecoder) {
        self.texts = decoder.decodeStringArrayForKey("t")
        self.dates = decoder.decodeInt32ArrayForKey("d")
    }

    public func encode(_ encoder: PostboxEncoder) {
        encoder.encodeStringArray(self.texts, forKey: "t")
        encoder.encodeInt32Array(self.dates, forKey: "d")
    }

    public static func ==(lhs: YepGramEditHistoryAttribute, rhs: YepGramEditHistoryAttribute) -> Bool {
        return lhs.texts == rhs.texts && lhs.dates == rhs.dates
    }
}

/// The server's copy of an edited message, carrying the stored history forward and, when the text
/// changed, the text it replaces. The server's copy never has the history, so it is always re-added.
func _internal_yepGramWithEditHistory(previous: Message, updated: StoreMessage) -> StoreMessage {
    let existing = previous.attributes.first(where: { $0 is YepGramEditHistoryAttribute }) as? YepGramEditHistoryAttribute
    var texts = existing?.texts ?? []
    var dates = existing?.dates ?? []
    if YepGramSettings.keepEditHistory && previous.text != updated.text && !previous.text.isEmpty {
        let writtenAt = (previous.attributes.first(where: { $0 is EditedMessageAttribute }) as? EditedMessageAttribute)?.date ?? previous.timestamp
        texts.append(previous.text)
        dates.append(writtenAt)
    }
    if texts.isEmpty {
        return updated
    }
    var attributes = updated.attributes.filter { !($0 is YepGramEditHistoryAttribute) }
    attributes.append(YepGramEditHistoryAttribute(texts: texts, dates: dates))
    return updated.withUpdatedAttributes(attributes)
}
