//
//  AnEmptyStateView.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

final class AnEmptyStateView: UIView {
  
  // MARK: - Outlets
  
  @IBOutlet private var rootView: UIView!
  @IBOutlet private weak var containerView: UIView!
  @IBOutlet private weak var titleIconImageView: UIImageView!
  @IBOutlet private weak var titleLabel: UILabel!
  @IBOutlet private weak var subtitleLabel: UILabel!
  
  // MARK: - Inspectable Properties
  
  @IBInspectable var titleText: String? {
    didSet { updateTitleLabel() }
  }
  
  @IBInspectable var subtitleText: String? {
    didSet { updateSubtitleLabel() }
  }
  
  @IBInspectable var titleIconName: String? {
    didSet {
      guard let iconName = titleIconName else { return }
      titleIcon = UIImage(systemName: iconName)
    }
  }
  
  @IBInspectable var inlineIconName: String? {
    didSet {
      guard let iconName = inlineIconName else { return }
      inlineIcon = UIImage(systemName: iconName)
      updateSubtitleLabel()
    }
  }
  
  @IBInspectable var titleIconColor: UIColor = .secondarySoft {
    didSet { titleIconImageView.tintColor = titleIconColor }
  }
  
  @IBInspectable var subtitleInlineIconColor: UIColor = .primaryMedium {
    didSet { updateSubtitleLabel() }
  }
  
  @IBInspectable var subtitleInlineIconSize: CGFloat = 20.0 {
    didSet { updateSubtitleLabel() }
  }
  
  // MARK: - Private Properties
  
  private var titleIcon: UIImage? {
    didSet {
      titleIconImageView.image = titleIcon?.withRenderingMode(.alwaysTemplate)
      titleIconImageView.tintColor = titleIconColor
    }
  }
  
  private var inlineIcon: UIImage?
  private let subtitleInlineIconToken = "{subtitleInlineIcon}"
  private var hasLoadedFromNib = false
  
  // MARK: - Lifecycle
  
  override init(frame: CGRect) {
    super.init(frame: frame)
    commonInit()
  }
  
  required init?(coder: NSCoder) {
    super.init(coder: coder)
    commonInit()
  }
  
  // MARK: - Private Functions
  
  private func commonInit() {
    guard !hasLoadedFromNib else { return }
    hasLoadedFromNib = true
    
    let bundle = Bundle(for: type(of: self))
    bundle.loadNibNamed(Self.className, owner: self)
    
    addSubview(rootView)
    rootView.frame = bounds
    rootView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
    
    titleIconImageView.tintColor = titleIconColor
  }
  
  private func updateTitleLabel() {
    titleLabel.text = titleText
  }
  
  private func updateSubtitleLabel() {
    subtitleLabel.attributedText = attributedSubtitle(from: subtitleText)
  }
  
  private func attributedSubtitle(from text: String?) -> NSAttributedString? {
    guard let text, !text.isEmpty else { return nil }
    
    let font = subtitleLabel.font ?? UIFont.systemFont(ofSize: 14.0)
    let textColor = subtitleLabel.textColor ?? UIColor.label
    let iconSize = subtitleInlineIconSize
    
    let components = text.components(separatedBy: subtitleInlineIconToken)
    let fullString = NSMutableAttributedString()
    let textAttributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: textColor]
    
    for (index, part) in components.enumerated() {
      fullString.append(NSAttributedString(string: part, attributes: textAttributes))
      
      if index < components.count - 1 {
        guard let inlineIcon else { continue }
        
        let symbolConfig = UIImage.SymbolConfiguration(pointSize: iconSize, weight: .regular)
        guard let iconImage = inlineIcon.applyingSymbolConfiguration(symbolConfig)?.withRenderingMode(.alwaysTemplate) else { continue }
        
        let imageView = UIImageView(image: iconImage)
        imageView.tintColor = subtitleInlineIconColor
        imageView.contentMode = .scaleAspectFit
        imageView.frame = CGRect(x: 0.0, y: 0.0, width: iconSize, height: iconSize)
        
        let renderer = UIGraphicsImageRenderer(size: imageView.bounds.size)
        let renderedImage = renderer.image { context in
          imageView.layer.render(in: context.cgContext)
        }
        let attachment = NSTextAttachment()
        attachment.image = renderedImage
        attachment.bounds = CGRect(x: 0.0, y: (font.capHeight - iconSize) / 2.0, width: iconSize, height: iconSize)
        
        fullString.append(NSAttributedString(string: " ", attributes: textAttributes))
        fullString.append(NSAttributedString(attachment: attachment))
        fullString.append(NSAttributedString(string: " ", attributes: textAttributes))
      }
    }
    
    return fullString
  }
}
