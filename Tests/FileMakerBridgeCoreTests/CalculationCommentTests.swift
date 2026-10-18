import XCTest
@testable import FileMakerBridgeCore

final class CalculationCommentTests: XCTestCase {
    let compiler = FileMakerXMLCompiler()

    func testCalculationCommentsBlockClipboardEvenInTemplateMode() {
        for source in [
            "Set Variable [ $result ; Value: /* Let ( [ x = 1 ] ; x + 2 ) */ ]",
            "Set Field [ Orders::Total ; 1 /* note */ + 2 ]",
            "If [ /* $value > 0 */ ]\nEnd If",
            "Perform Script [ \"Process\" ; Parameter: /* JSONSetElement ( \"{}\" ; \"id\" ; $id ; JSONString ) */ ]",
            "Insert from URL [ Target: $result ; URL: $url ; cURL options: $curl // note ]",
            "Set Variable [ $x ; Value: Case ( $test ; 1 ; 0 ) // note ]"
        ] {
            for templates in [true, false] {
                let result = compiler.compile(source, options: .init(convertUnsupportedLinesToComments: templates))
                XCTAssertGreaterThan(result.errorCount, 0, source)
                XCTAssertFalse(result.canCopyToFileMaker, source)
                XCTAssertTrue(result.issues.contains { $0.message == CalculationComments.message }, source)
            }
        }
    }

    func testWholeCalculationWrapperRepairKeepsNamesAndBusinessLogic() throws {
        let calculation = "Let ( [ amount = Orders::Total ; rate = $taxRate ] ; amount * ( 1 + rate ) )"
        let source = "# before\nSet Variable [ $gross ; Value: /*" + calculation + "*/ ]\nGo to Layout [ \"Order Detail\" ]"
        var review = SmartFixReview(source: source)
        XCTAssertEqual(review.items.count, 1)
        XCTAssertEqual(review.items[0].suggestion, "Set Variable [ $gross ; Value: " + calculation + " ]")
        review.items[0].action = .replace
        XCTAssertEqual(try review.applying(to: source), source.replacingOccurrences(of: "/*", with: "").replacingOccurrences(of: "*/", with: ""))
    }

    func testIfAndElseIfWrapperRepairsPreserveWorkflow() throws {
        let source = "If [ /*$x = 1*/ ]\nSet Variable [ $result ; Value: 10 ]\nElse If [ /*$x = 2*/ ]\nSet Variable [ $result ; Value: 20 ]\nEnd If"
        var review = SmartFixReview(source: source)
        XCTAssertEqual(review.items.count, 2)
        for i in review.items.indices {
            XCTAssertNotNil(review.items[i].suggestion)
            review.items[i].action = .replace
        }
        let fixed = try review.applying(to: source)
        XCTAssertEqual(fixed, source.replacingOccurrences(of: "/*", with: "").replacingOccurrences(of: "*/", with: ""))
        XCTAssertEqual(compiler.compile(fixed).errorCount, 0)
    }

    func testQuotedCommentMarkersURLsAndScriptCommentsAreData() {
        let source = #"""
        # Explain /* a wrapper */ or // a comment here
        Set Variable [ $url ; Value: "https://example.com/path" ]
        Set Variable [ $text ; Value: "/* keep this text */ // also data" ]
        Set Variable [ $escaped ; Value: "quoted \" // still text" ]
        Insert from URL [ Target: $result ; URL: "https://example.com" ; cURL options: "--header " & Quote ( "https://example.com/*" ) ]
        """#
        let result = compiler.compile(source)
        XCTAssertEqual(result.errorCount, 0)
        XCTAssertEqual(result.warningCount, 0)
        XCTAssertTrue(result.xml.contains("https://example.com/*"))
        XCTAssertTrue(SmartFixReview(source: source).items.isEmpty)
    }

    func testMixedInlineLineAndUnterminatedCommentsRequireManualReview() {
        for calculation in ["1 /* note */ + 2", "1 // explanation", "/* missing end", "/* 1 */ + /* 2 */", "/* 1 // unclear */"] {
            let review = SmartFixReview(source: "Set Variable [ $value ; Value: \(calculation) ]")
            XCTAssertEqual(review.items.count, 1)
            XCTAssertNil(review.items[0].suggestion, calculation)
        }
    }

    func testPreservedNativeCalculationsCannotBypassRule() {
        let xml = "<Step enable=\"True\" id=\"999\" name=\"Future\"><Calculation><![CDATA[1 /* note */]]></Calculation></Step>"
        let imported = FileMakerXMLDecompiler().decompile("<fmxmlsnippet type=\"FMObjectList\">\(xml)</fmxmlsnippet>")
        let result = compiler.compile(imported.text, preservedSteps: imported.preservedSteps)
        XCTAssertFalse(result.canCopyToFileMaker)
        XCTAssertGreaterThan(result.errorCount, 0)
    }

    func testWrapperRepairDoesNotAlterMatchingStringData() throws {
        let source = "Set Variable [ $x ; Value: /*1*/ ; Repetition: Case ( \"/*1*/\" = $text ; 1 ; 2 ) ]"
        let review = SmartFixReview(source: source)
        XCTAssertEqual(review.items.first?.suggestion, "Set Variable [ $x ; Value: 1 ; Repetition: Case ( \"/*1*/\" = $text ; 1 ; 2 ) ]")
    }
}
