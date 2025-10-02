//
//  UIImage+Initials.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension UIImage {
  
  static func initialsImage(displayName: String,
                            diameter: CGFloat,
                            backgroundColor: UIColor,
                            borderColor: UIColor = .clear,
                            borderWidth: CGFloat = 0.0,
                            initialsColor: UIColor = .white,
                            fontSizeRatio: CGFloat = 0.4) -> UIImage? {
    let parts = displayName.split { $0 == "," }.map { String($0).trimmed() }.filter { !$0.isEmpty }
    let initials = parts.compactMap { $0.first }.map { String($0) }.joined().uppercased()
    
    let renderer = UIGraphicsImageRenderer(size: CGSize(width: diameter, height: diameter))
    return renderer.image { _ in
      let bounds = CGRect(x: 0.0, y: 0.0, width: diameter, height: diameter)
      let inset = borderWidth / 2.0
      let path = UIBezierPath(ovalIn: bounds.insetBy(dx: inset, dy: inset))
      
      backgroundColor.setFill()
      path.fill()
      
      if borderWidth > 0.0 {
        borderColor.setStroke()
        path.lineWidth = borderWidth
        path.stroke()
      }
      
      let font = UIFont.systemFont(ofSize: diameter * fontSizeRatio, weight: .medium)
      let attributes: [NSAttributedString.Key: Any] = [.foregroundColor: initialsColor, .font: font]
      
      let textSize = initials.size(withAttributes: attributes)
      let textRect = CGRect(
        x: (diameter - textSize.width) / 2.0,
        y: (diameter - textSize.height) / 2.0,
        width: textSize.width,
        height: textSize.height
      )
      
      initials.draw(in: textRect, withAttributes: attributes)
    }
  }
}
