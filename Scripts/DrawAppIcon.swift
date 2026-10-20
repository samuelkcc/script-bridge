import AppKit

// Original bridge symbol, matching Desktop/web/icons.js. No third-party art.
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1024, pixelsHigh: 1024,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 4096, bitsPerPixel: 32)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
NSColor.clear.setFill()
NSRect(x: 0, y: 0, width: 1024, height: 1024).fill()
let tile = NSBezierPath(roundedRect: NSRect(x: 64, y: 64, width: 896, height: 896),
    xRadius: 200, yRadius: 200)
NSGradient(starting: NSColor(srgbRed: 0.443, green: 0.341, blue: 0.722, alpha: 1),
    ending: NSColor(srgbRed: 0.329, green: 0.239, blue: 0.592, alpha: 1))!.draw(in: tile, angle: -45)
let symbol = NSBezierPath()
func point(_ x: CGFloat, _ y: CGFloat) -> NSPoint { NSPoint(x: 152 + x * 30, y: 152 + (24 - y) * 30) }
for points: [(CGFloat, CGFloat)] in [
    [(3, 8), (15, 8)], [(11, 4), (15, 8), (11, 12)],
    [(21, 16), (9, 16)], [(13, 12), (9, 16), (13, 20)]
] {
    symbol.move(to: point(points[0].0, points[0].1))
    for p in points.dropFirst() { symbol.line(to: point(p.0, p.1)) }
}
symbol.lineWidth = 54
symbol.lineCapStyle = .round
symbol.lineJoinStyle = .round
NSColor.white.setStroke()
symbol.stroke()
NSGraphicsContext.restoreGraphicsState()
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
