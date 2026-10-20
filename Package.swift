// swift-tools-version: 6.0
import PackageDescription

var products: [Product] = [
    .library(name: "FileMakerBridgeCore", targets: ["FileMakerBridgeCore"]),
    .executable(name: "FileMakerBridgeWorker", targets: ["FileMakerBridgeWorker"])
]
var targets: [Target] = [
    .target(name: "FileMakerBridgeCore"),
    .executableTarget(name: "FileMakerBridgeWorker", dependencies: ["FileMakerBridgeCore"]),
    .testTarget(name: "FileMakerBridgeCoreTests", dependencies: ["FileMakerBridgeCore"])
]
// The shared conversion worker builds without SwiftUI or AppKit on Windows.
#if os(macOS)
products.append(.executable(name: "FileMakerScriptBridge", targets: ["FileMakerScriptBridgeApp"]))
targets.append(.executableTarget(name: "FileMakerScriptBridgeApp", dependencies: ["FileMakerBridgeCore"]))
targets.append(.testTarget(name: "FileMakerScriptBridgeAppTests", dependencies: ["FileMakerScriptBridgeApp", "FileMakerBridgeCore"]))
#endif

let package = Package(name: "FileMakerScriptBridge", platforms: [.macOS(.v13)], products: products, targets: targets)
