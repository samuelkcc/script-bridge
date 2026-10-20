import Foundation
import FileMakerBridgeCore

// JSON lines over stdio. State (including locked native XML) lives only in this
// process. The desktop host keeps it alive and never retries a failed session.
final class Worker {
    var preserved: [String: PreservedFileMakerStep] = [:]
    var review: SmartFixReview?
    let compiler = FileMakerXMLCompiler()

    func compilation(_ source: String, templates: Bool) -> [String: Any] {
        let result = compiler.compile(source, options: .init(convertUnsupportedLinesToComments: templates), preservedSteps: preserved)
        let legacy = ReviewMarkerDetector.count(in: source)
        return ["source": source, "xml": result.xml, "stepCount": result.steps.count,
                "supportedCount": result.supportedStepCount, "templateCount": result.commentFallbackCount,
                "preservedCount": result.preservedStepCount, "errorCount": result.errorCount,
                "warningCount": result.warningCount, "reviewOnlyCount": legacy,
                "canCopy": result.canCopyToFileMaker && legacy == 0,
                "issues": result.issues.map { ["line": $0.line, "severity": $0.severity.rawValue, "message": $0.message, "source": $0.source] as [String: Any] }]
    }

    func handle(_ request: [String: Any]) throws -> [String: Any] {
        let source = request["source"] as? String ?? ""
        guard source.utf8.count <= 4 * 1024 * 1024 else { throw fault("Script exceeds the 4 MB editor limit.") }
        let templates = request["templates"] as? Bool ?? true
        switch request["op"] as? String {
        case "hello":
            return ["protocol": 1, "engine": "Swift", "example": ExampleScript.fileMaker26,
                    "catalogue": FileMakerScriptStepCatalog.entries.map {
                        ["name": $0.name, "category": $0.category, "url": $0.documentationURL.absoluteString, "support": $0.support.rawValue]
                    }]
        case "compile": return compilation(source, templates: templates)
        case "reset":
            preserved = [:]; review = nil
            return compilation("", templates: templates)
        case "decompile":
            let xml = request["xml"] as? String ?? ""
            guard xml.utf8.count <= 16 * 1024 * 1024 else { throw fault("Clipboard XML exceeds the 16 MB limit.") }
            let result = FileMakerXMLDecompiler().decompile(xml)
            guard result.isSuccessful else { throw fault(result.warnings.first ?? "No native FileMaker script was found.") }
            preserved = result.preservedSteps; review = nil
            var response = compilation(result.text, templates: templates)
            response["importedXML"] = xml
            response["importWarnings"] = result.warnings
            return response
        case "review":
            let snapshot = SmartFixReview(source: source, preservedSteps: preserved)
            review = snapshot
            return ["source": source, "items": snapshot.items.map { item in
                ["line": item.line, "endLine": item.endLine, "original": item.original, "reason": item.reason,
                 "suggestion": item.suggestion as Any? ?? NSNull(), "replacement": item.replacement,
                 "questions": item.questions.map { ["key": $0.key, "prompt": $0.prompt, "choices": $0.choices] as [String: Any] }] as [String: Any]
            }]
        case "applyFixes":
            guard var snapshot = review, snapshot.source == source else { throw SmartFixError.staleReview }
            let choices = request["choices"] as? [[String: Any]] ?? []
            var seen = Set<Int>()
            for choice in choices {
                guard let line = choice["line"] as? Int, seen.insert(line).inserted,
                      let index = snapshot.items.firstIndex(where: { $0.line == line }) else { throw fault("Invalid or duplicate Smart Fix choice.") }
                switch choice["action"] as? String {
                case "replace":
                    snapshot.items[index].replacement = choice["replacement"] as? String ?? ""
                    snapshot.items[index].action = .replace
                case "answers":
                    let answers = choice["answers"] as? [String: String] ?? [:]
                    for q in snapshot.items[index].questions.indices {
                        snapshot.items[index].questions[q].answer = answers[snapshot.items[index].questions[q].key] ?? ""
                    }
                    guard snapshot.items[index].useAnswers() else { throw fault("Complete the questions for line \(line) with valid native options.") }
                case "omit": snapshot.items[index].action = .omit
                case "keep": break
                default: throw fault("Unknown Smart Fix action.")
                }
            }
            let updated = try snapshot.applying(to: source)
            let before = compiler.compile(source, options: .init(convertUnsupportedLinesToComments: templates), preservedSteps: preserved)
            let after = compiler.compile(updated, options: .init(convertUnsupportedLinesToComments: templates), preservedSteps: preserved)
            var oldErrors = before.issues.filter { $0.severity == .error }.map { $0.message + "\n" + $0.source }
            for issue in after.issues where issue.severity == .error {
                guard let index = oldErrors.firstIndex(of: issue.message + "\n" + issue.source) else { throw fault("These choices introduce blocking errors. Revise the replacements.") }
                oldErrors.remove(at: index)
            }
            review = nil
            return compilation(updated, templates: templates)
        default: throw fault("Unsupported worker operation.")
        }
    }
    func fault(_ message: String) -> NSError { NSError(domain: "BridgeWorker", code: 1, userInfo: [NSLocalizedDescriptionKey: message]) }
}

let worker = Worker()
while let line = readLine() {
    do {
        guard line.utf8.count <= 24 * 1024 * 1024,
              let data = line.data(using: .utf8),
              let request = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw worker.fault("Invalid JSON request.") }
        let response = try worker.handle(request)
        let encoded = try JSONSerialization.data(withJSONObject: ["ok": true, "result": response], options: [.sortedKeys])
        FileHandle.standardOutput.write(encoded + Data([10]))
    } catch {
        let encoded = try! JSONSerialization.data(withJSONObject: ["ok": false, "error": error.localizedDescription])
        FileHandle.standardOutput.write(encoded + Data([10]))
    }
}
