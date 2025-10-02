//
//  AnSegmentedControl.swift
//  A360Scribe
//
//  Created by Mike Grankin on 13.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
final class AnSegmentedControl: UIControl {
  
  // MARK: - IBInspectable Properties
  
  @IBInspectable var selectedColor: UIColor = .primarySoft {
    didSet {
      underlineView.backgroundColor = selectedColor
      updateSelection(animated: false)
      badgeViews.forEach { $0.backgroundColor = selectedColor }
      leftEdgeIndicatorButton.backgroundColor = selectedColor
      rightEdgeIndicatorButton.backgroundColor = selectedColor
    }
  }
  
  @IBInspectable var unselectedColor: UIColor = .textSecondary {
    didSet {
      updateSelection(animated: false)
    }
  }
  
  @IBInspectable var bottomLineColor: UIColor = .textSecondary.withAlphaComponent(0.3) {
    didSet {
      bottomLineView.backgroundColor = bottomLineColor
    }
  }
  
  @IBInspectable var underlineHeight: CGFloat = 2.0 {
    didSet {
      setNeedsLayout()
    }
  }
  
  @IBInspectable var fontSize: CGFloat = 16.0 {
    didSet {
      rebuildItems()
    }
  }
  
  @IBInspectable var itemTitles: String = "" {
    didSet {
      rebuildItems()
    }
  }
  
  @IBInspectable var itemIconNames: String = "" {
    didSet {
      rebuildItems()
    }
  }
  
  @IBInspectable var isScrollable: Bool = true
  
  // MARK: - Public Properties
  
  var currentSegmentDetails: (title: String, iconName: String?)? {
    guard items.indices.contains(selectedIndex) else { return nil }
    let item = items[selectedIndex]
    return (title: item.title, iconName: item.iconName)
  }
  
  // MARK: - Private Properties
  
  internal var buttons: [UIButton] = []
  internal var badgeViews: [UIView] = []
  internal let scrollView = UIScrollView()
  private let stackView = UIStackView()
  internal let underlineView = UIView()
  private let bottomLineView = UIView()
  internal var badgedIndices: Set<Int> = []
  internal let leftEdgeIndicatorButton = AnSegmentedControl.createEdgeButton()
  internal let rightEdgeIndicatorButton = AnSegmentedControl.createEdgeButton()
  internal var underlineLeadingConstraint: NSLayoutConstraint?
  internal var underlineTrailingConstraint: NSLayoutConstraint?
  
  private(set) var selectedIndex: Int = 0
  
  internal var items: [(title: String, icon: UIImage?, iconName: String?)] = [] {
    didSet {
      configureButtons()
    }
  }
  
  private var isScrollableEffective: Bool {
    guard !buttons.isEmpty, isScrollable else { return false }
    let spacing: CGFloat = 16.0
    let totalContentWidth = buttons.map { $0.intrinsicContentSize.width + 24.0 }.reduce(0, +) + spacing * CGFloat(buttons.count - 1)
    return totalContentWidth > bounds.width
  }
  
  private var stackConstraintsActive = false
  
  // MARK: - Initializers
  
  override init(frame: CGRect) {
    super.init(frame: frame)
    commonInit()
  }
  
  required init?(coder: NSCoder) {
    super.init(coder: coder)
    commonInit()
  }
  
  private func commonInit() {
    backgroundColor = .clear
    
    scrollView.showsHorizontalScrollIndicator = false
    scrollView.showsVerticalScrollIndicator = false
    scrollView.bounces = true
    scrollView.isScrollEnabled = true
    scrollView.translatesAutoresizingMaskIntoConstraints = false
    scrollView.delegate = self
    addSubview(scrollView)
    
    stackView.axis = .horizontal
    stackView.alignment = .center
    stackView.distribution = .fill
    stackView.spacing = 16.0
    stackView.translatesAutoresizingMaskIntoConstraints = false
    scrollView.addSubview(stackView)
    
    underlineView.backgroundColor = selectedColor
    underlineView.translatesAutoresizingMaskIntoConstraints = false
    scrollView.addSubview(underlineView)
    
    bottomLineView.backgroundColor = bottomLineColor
    bottomLineView.translatesAutoresizingMaskIntoConstraints = false
    addSubview(bottomLineView)
    
    leftEdgeIndicatorButton.addTarget(self, action: #selector(didTapLeftIndicator), for: .touchUpInside)
    rightEdgeIndicatorButton.addTarget(self, action: #selector(didTapRightIndicator), for: .touchUpInside)
    addSubview(leftEdgeIndicatorButton)
    addSubview(rightEdgeIndicatorButton)
    
    NSLayoutConstraint.activate([scrollView.topAnchor.constraint(equalTo: topAnchor),
                                 scrollView.leadingAnchor.constraint(equalTo: leadingAnchor),
                                 scrollView.trailingAnchor.constraint(equalTo: trailingAnchor),
                                 scrollView.bottomAnchor.constraint(equalTo: bottomAnchor),
                                 leftEdgeIndicatorButton.widthAnchor.constraint(equalToConstant: 22.0),
                                 leftEdgeIndicatorButton.heightAnchor.constraint(equalToConstant: 22.0),
                                 leftEdgeIndicatorButton.centerYAnchor.constraint(equalTo: centerYAnchor),
                                 leftEdgeIndicatorButton.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 4.0),
                                 rightEdgeIndicatorButton.widthAnchor.constraint(equalToConstant: 22.0),
                                 rightEdgeIndicatorButton.heightAnchor.constraint(equalToConstant: 22.0),
                                 rightEdgeIndicatorButton.centerYAnchor.constraint(equalTo: centerYAnchor),
                                 rightEdgeIndicatorButton.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -4.0),
                                 bottomLineView.leadingAnchor.constraint(equalTo: leadingAnchor),
                                 bottomLineView.trailingAnchor.constraint(equalTo: trailingAnchor),
                                 bottomLineView.heightAnchor.constraint(equalToConstant: 1.0),
                                 bottomLineView.bottomAnchor.constraint(equalTo: bottomAnchor),
                                 underlineView.bottomAnchor.constraint(equalTo: scrollView.frameLayoutGuide.bottomAnchor),
                                 underlineView.heightAnchor.constraint(equalToConstant: underlineHeight)
                                ])
  }
  
  // MARK: - Layout
  
  override func layoutSubviews() {
    super.layoutSubviews()
    
    stackView.spacing = isScrollableEffective ? stackView.spacing : 0.0
    stackView.distribution = isScrollableEffective ? .fill : .fillEqually
    
    if !stackConstraintsActive {
      var anchorConstraints = [stackView.topAnchor.constraint(equalTo: scrollView.topAnchor),
                               stackView.bottomAnchor.constraint(equalTo: scrollView.bottomAnchor),
                               stackView.leadingAnchor.constraint(equalTo: scrollView.leadingAnchor),
                               stackView.trailingAnchor.constraint(equalTo: scrollView.trailingAnchor),
                               stackView.heightAnchor.constraint(equalTo: scrollView.heightAnchor)]
      
      if !isScrollableEffective {
        anchorConstraints.append(stackView.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor))
      }
      
      NSLayoutConstraint.activate(anchorConstraints)
      stackConstraintsActive = true
      scrollView.layoutIfNeeded()
      stackView.layoutIfNeeded()
    }
    
    updateUnderlinePosition(animated: false)
  }
  
  // MARK: - Public Functions
  
  func hideSegments(withTitles hiddenTitles: [String]) {
    let titles = itemTitles.components(separatedBy: ",").map { $0.trimmed() }
    let icons = itemIconNames.components(separatedBy: ",").map { $0.trimmed() }
    let pairs = zip(titles, icons).map { (title: $0.0, icon: $0.1) }
    let keptPairs = pairs.filter { !hiddenTitles.contains($0.title) }
    itemTitles = keptPairs.map { $0.title }.joined(separator: ",")
    itemIconNames = keptPairs.map { $0.icon }.joined(separator: ",")
  }
  
  func selectSegment(at index: Int, animated: Bool = true, force: Bool = false) {
    guard buttons.indices.contains(index), index != selectedIndex || force else { return }
    
    selectedIndex = index
    updateSelection(animated: animated)
    scrollToSelected(animated: animated)
    setBadge(visible: false, at: index)
    sendActions(for: .valueChanged)
  }
  
  func animateSegment(at index: Int) {
    guard buttons.indices.contains(index), index != selectedIndex else { return }
    
    let button = buttons[index]
    button.imageView?.addSymbolEffect(.bounce.down, options: .nonRepeating, animated: true) { [weak self, weak button] _ in
      button?.imageView?.removeAllSymbolEffects()
      self?.setBadge(visible: true, at: index)
    }
  }
  
  func animateSegment(withTitle title: String) {
    guard let index = indexOfSegment(withTitle: title) else { return }
    animateSegment(at: index)
  }
  
  func selectSegment(withTitle title: String, animated: Bool = true, force: Bool = false) {
    guard let index = indexOfSegment(withTitle: title) else { return }
    selectSegment(at: index, animated: animated, force: force)
  }
  
  // MARK: - Private Functions
  
  private func rebuildItems() {
    let titles = itemTitles.components(separatedBy: ",").map { $0.trimmed() }
    let icons = itemIconNames.components(separatedBy: ",").map { $0.trimmed() }
    
    guard !titles.isEmpty else {
      print("AnSegmentedControl: No segments configured. Check `itemTitles`.")
      return
    }
    
    var newItems: [(title: String, icon: UIImage?, iconName: String?)] = []
    
    for (index, title) in titles.enumerated() {
      if index < icons.count,
         !icons[index].isEmpty,
         let icon = UIImage(systemName: icons[index]) ?? UIImage(named: icons[index]) {
        newItems.append((title: title, icon: icon, iconName: icons[index]))
      } else {
        newItems.append((title: title, icon: nil, iconName: nil))
      }
    }
    
    items = newItems
  }
  
  private func configureButtons() {
    buttons.forEach { $0.removeFromSuperview() }
    stackView.arrangedSubviews.forEach { $0.removeFromSuperview() }
    buttons.removeAll()
    badgeViews.forEach { $0.removeFromSuperview() }
    badgeViews.removeAll()
    stackConstraintsActive = false
    
    for (index, item) in items.enumerated() {
      let button = UIButton(type: .system)
      var config = UIButton.Configuration.plain()
      config.title = item.title
      config.image = item.icon
      config.preferredSymbolConfigurationForImage = .init(pointSize: fontSize, weight: .medium)
      config.imagePlacement = .leading
      config.imagePadding = 4.0
      config.baseForegroundColor = unselectedColor
      config.contentInsets = NSDirectionalEdgeInsets(top: 0.0, leading: 8.0, bottom: underlineHeight, trailing: 8.0)
      config.titleLineBreakMode = .byTruncatingTail
      config.titleTextAttributesTransformer = UIConfigurationTextAttributesTransformer { [weak self] incoming in
        guard let self else { return incoming }
        var outgoing = incoming
        outgoing.font = UIFont(name: "PlusJakartaSans-Regular_Medium", size: fontSize) ?? UIFont.systemFont(ofSize: fontSize, weight: .medium)
        return outgoing
      }
      
      button.configuration = config
      button.tag = index
      button.addAction(UIAction { [weak self] _ in self?.selectSegment(at: index) }, for: .touchUpInside)
      
      stackView.addArrangedSubview(button)
      
      button.translatesAutoresizingMaskIntoConstraints = false
      button.setContentHuggingPriority(.required, for: .horizontal)
      button.setContentCompressionResistancePriority(.required, for: .horizontal)
      button.heightAnchor.constraint(equalTo: scrollView.heightAnchor).isActive = true
      if isScrollableEffective {
        let buttonWidth = button.intrinsicContentSize.width
        button.widthAnchor.constraint(equalToConstant: buttonWidth).isActive = true
      }
      
      buttons.append(button)
      let badge = createBadgeView()
      scrollView.addSubview(badge)
      badgeViews.append(badge)
      if item.icon != nil, let imageView = button.imageView {
        NSLayoutConstraint.activate([badge.widthAnchor.constraint(equalToConstant: 8.0),
                                     badge.heightAnchor.constraint(equalToConstant: 8.0),
                                     badge.centerXAnchor.constraint(equalTo: imageView.trailingAnchor, constant: -4.0),
                                     badge.centerYAnchor.constraint(equalTo: imageView.topAnchor, constant: 2.0)])
      }
    }
    
    updateSelection(animated: false)
  }
  
  private func indexOfSegment(withTitle title: String) -> Int? {
    return items.firstIndex { $0.title == title }
  }
}

// MARK: - UIScrollViewDelegate

extension AnSegmentedControl: UIScrollViewDelegate {
  func scrollViewDidScroll(_ scrollView: UIScrollView) {
    guard scrollView.isDragging || scrollView.isDecelerating else { return }
    updateEdgeIndicators()
  }
  
  func scrollViewDidEndScrollingAnimation(_ scrollView: UIScrollView) {
    updateEdgeIndicators()
  }
}
