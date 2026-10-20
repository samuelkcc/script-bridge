import Foundation
#if canImport(FoundationXML)
import FoundationXML
#endif

/// Inspect actual calculation nodes, not paths, quoted data, or script Comment steps.
enum CalculationComments {
    static let message = "Comments are not allowed inside calculations. Use a separate # script Comment step. Smart Fix can unwrap a calculation enclosed in /* ... */ without deleting its contents; other comments need manual review."

    static func violations(in step: CompiledStep) -> [String] {
        calculations(in: step).filter { !commentRanges(in: $0).isEmpty }
    }

    static func calculations(in step: CompiledStep) -> [String] {
        if case .comment = step { return [] }
        let xml = FileMakerXMLCompiler().renderDocument([step])
        let reader = CalculationReader()
        let parser = XMLParser(data: Data(xml.utf8))
        parser.delegate = reader
        guard parser.parse() else { return [] }
        return reader.values
    }

    static func repair(_ text: String, step: CompiledStep) -> String? {
        let calculations = violations(in: step)
        guard !calculations.isEmpty else { return nil }
        var replacements: [String: String] = [:]
        for calculation in calculations {
            let value = calculation.trimmingCharacters(in: .whitespacesAndNewlines)
            let ranges = commentRanges(in: value)
            guard value.hasPrefix("/*"), value.hasSuffix("*/"), ranges.count == 1,
                  ranges[0] == value.startIndex..<value.endIndex else { return nil }
            let inner = String(value.dropFirst(2).dropLast(2))
            guard !inner.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  commentRanges(in: inner).isEmpty else { return nil }
            replacements[value] = inner
        }
        var repaired = text
        var found = Set<String>()
        // Only replace actual comments outside quoted text, never matching string data.
        for range in commentRanges(in: text).reversed() {
            let original = String(text[range])
            guard let replacement = replacements[original] else { return nil }
            repaired.replaceSubrange(range, with: replacement)
            found.insert(original)
        }
        return found == Set(replacements.keys) ? repaired : nil
    }

    static func commentRanges(in text: String) -> [Range<String.Index>] {
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
            } else if character == "/", next < text.endIndex {
                if text[next] == "*" {
                    let end = text.range(of: "*/", range: text.index(after: next)..<text.endIndex)?.upperBound ?? text.endIndex
                    ranges.append(index..<end)
                    index = end
                    continue
                }
                if text[next] == "/" {
                    let end = text[next...].firstIndex(of: "\n") ?? text.endIndex
                    ranges.append(index..<end)
                    index = end
                    continue
                }
            }
            index = next
        }
        return ranges
    }
}

private final class CalculationReader: NSObject, XMLParserDelegate {
    var values: [String] = []
    private var current: String?

    func parser(_ parser: XMLParser, didStartElement name: String, namespaceURI: String?, qualifiedName: String?, attributes: [String: String]) {
        if name == "Calculation" { current = "" }
    }
    func parser(_ parser: XMLParser, foundCharacters string: String) { current? += string }
    func parser(_ parser: XMLParser, foundCDATA data: Data) { current? += String(decoding: data, as: UTF8.self) }
    func parser(_ parser: XMLParser, didEndElement name: String, namespaceURI: String?, qualifiedName: String?) {
        if name == "Calculation", let value = current { values.append(value); current = nil }
    }
}
