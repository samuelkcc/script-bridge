import Foundation

enum CalculationFieldReferences {
    static let message = "Whitespace after :: can make FileMaker treat the field name as missing and wrap the calculation in /* ... */ when pasted. Smart Fix can remove this separator whitespace; verify the field name in FileMaker."

    static func violations(in step: CompiledStep) -> Bool {
        CalculationComments.calculations(in: step).contains { !whitespaceRanges(in: $0).isEmpty }
    }

    static func repair(_ text: String) -> String {
        var result = text
        for range in whitespaceRanges(in: text).reversed() { result.removeSubrange(range) }
        return result
    }

    // Remove only the separator whitespace introduced by joining two physical lines.
    static func joining(_ first: String, _ second: String) -> String {
        var result = first + " " + second
        let boundary = result.index(result.startIndex, offsetBy: first.count)
        if let range = whitespaceRanges(in: result).first(where: { $0.lowerBound == boundary }) {
            result.removeSubrange(range)
        }
        return result
    }

    private static func whitespaceRanges(in text: String) -> [Range<String.Index>] {
        var ranges: [Range<String.Index>] = []
        var index = text.startIndex
        var quote: Character?
        while index < text.endIndex {
            let character = text[index]
            let next = text.index(after: index)
            if let closing = quote {
                if character == "\\", next < text.endIndex {
                    index = text.index(after: next)
                    continue
                }
                if character == closing { quote = nil }
            } else if character == "\"" || character == "“" || character == "‘" {
                quote = character == "“" ? "”" : character == "‘" ? "’" : "\""
            } else if character == "/", next < text.endIndex, text[next] == "*" {
                index = text.range(of: "*/", range: text.index(after: next)..<text.endIndex)?.upperBound ?? text.endIndex
                continue
            } else if character == "/", next < text.endIndex, text[next] == "/" {
                index = text[next...].firstIndex(of: "\n") ?? text.endIndex
                continue
            } else if character == ":", next < text.endIndex, text[next] == ":" {
                let start = text.index(after: next)
                var end = start
                while end < text.endIndex, text[end].isWhitespace { end = text.index(after: end) }
                if start < end { ranges.append(start..<end) }
                index = end
                continue
            }
            index = next
        }
        return ranges
    }
}
