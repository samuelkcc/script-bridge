import XCTest
@testable import FileMakerBridgeCore

final class CalculationFieldReferenceTests: XCTestCase {
    func testAIFieldReferencesSplitAfterSeparatorDoNotAcquireLeadingSpace() {
        let source = """
        Set Variable [ $emailReceiver ; Value:
          Trim ( GetAsText ( email_receiver::
            nav_price_approval_release ) )
        ]
        Set Variable [ $vestePart ; Value: dk_approval_db_price::
          Veste Part ]
        Set Variable [ $sourceData ; Value: JSONSetElement ( "{}" ;
          [ "description" ; dk_approval_db_price::
            Description ; JSONString ] ;
          [ "brand" ; Upper ( Trim ( dk_approval_db_price::
            Brand ) ) ; JSONString ] ) ]
        """
        let result = FileMakerXMLCompiler().compile(source)
        XCTAssertEqual(result.errorCount, 0)
        XCTAssertTrue(result.xml.contains("email_receiver::nav_price_approval_release"))
        XCTAssertTrue(result.xml.contains("dk_approval_db_price::Veste Part"))
        XCTAssertTrue(result.xml.contains("dk_approval_db_price::Description"))
        XCTAssertFalse(result.xml.contains(":: "))
    }

    func testExplicitSeparatorWhitespaceRequiresReviewAndSmartFixRepairsIt() throws {
        let source = "Set Variable [ $value ; Value: Orders:: Total Price ]"
        for templates in [true, false] {
            XCTAssertFalse(FileMakerXMLCompiler().compile(source, options: .init(convertUnsupportedLinesToComments: templates)).canCopyToFileMaker)
        }
        var review = SmartFixReview(source: source)
        XCTAssertEqual(review.items.count, 1)
        XCTAssertEqual(review.items[0].suggestion, "Set Variable [ $value ; Value: Orders::Total Price ]")
        review.items[0].action = .replace
        XCTAssertTrue(FileMakerXMLCompiler().compile(try review.applying(to: source)).canCopyToFileMaker)
    }

    func testFileMakerAddedWrapperAndInvalidSeparatorAreRepairedTogether() throws {
        let source = "Set Variable [ $value ; Value: /*JSONSetElement ( \"{}\" ; \"brand\" ; Upper ( Trim ( Orders:: Brand ) ) ; JSONString )*/ ]"
        let expected = "Set Variable [ $value ; Value: JSONSetElement ( \"{}\" ; \"brand\" ; Upper ( Trim ( Orders::Brand ) ) ; JSONString ) ]"
        let review = SmartFixReview(source: source)
        XCTAssertEqual(review.items.first?.suggestion, expected)
        XCTAssertTrue(FileMakerXMLCompiler().compile(expected).canCopyToFileMaker)
    }

    func testLiteralAndCommentTextAndSpacesWithinFieldNamesArePreserved() {
        let source = """
        # Orders:: Total Price is documentation
        Set Variable [ $value ; Value: Orders::Total Price ]
        Set Variable [ $text ; Value: "Orders::
          Total Price" ]
        """
        let result = FileMakerXMLCompiler().compile(source)
        XCTAssertEqual(result.errorCount, 0)
        XCTAssertTrue(result.xml.contains("\"Orders:: Total Price\""))
        XCTAssertTrue(result.xml.contains("Orders:: Total Price is documentation"))
        XCTAssertEqual(CalculationFieldReferences.repair(#"Orders:: Total & "Orders:: Total \" Orders:: Other""#), #"Orders::Total & "Orders:: Total \" Orders:: Other""#)
    }
}
