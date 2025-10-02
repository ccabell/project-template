//
//  AnSegmentedControl+Helpers.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.06.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

// MARK: - AnSegmentedControl Helpers

internal extension AnSegmentedControl {
  
  func updateSelection(animated: Bool) {
    for (index, button) in buttons.enumerated() {
      var config = button.configuration
      config?.baseForegroundColor = index == selectedIndex ? selectedColor : unselectedColor
      button.configuration = config
    }
    updateUnderlinePosition(animated: animated)
  }
  
  func updateUnderlinePosition(animated: Bool) {
    guard buttons.indices.contains(selectedIndex) else { return }
    let selectedButton = buttons[selectedIndex]

    underlineLeadingConstraint?.isActive = false
    underlineTrailingConstraint?.isActive = false
    underlineLeadingConstraint = underlineView.leadingAnchor.constraint(equalTo: selectedButton.leadingAnchor)
    underlineTrailingConstraint = underlineView.trailingAnchor.constraint(equalTo: selectedButton.trailingAnchor)
    underlineLeadingConstraint?.isActive = true
    underlineTrailingConstraint?.isActive = true

    guard animated else { return }
    UIView.animate(withDuration: 0.25) {
      self.layoutIfNeeded()
    }
  }
  
  func scrollToSelected(animated: Bool) {
    guard buttons.indices.contains(selectedIndex) else { return }
    let frame = buttons[selectedIndex].frame.insetBy(dx: -16.0, dy: 0.0)
    scrollView.scrollRectToVisible(frame, animated: animated)
  }
  
  func createBadgeView() -> UIView {
    let badge = UIView()
    badge.translatesAutoresizingMaskIntoConstraints = false
    badge.backgroundColor = selectedColor
    badge.layer.cornerRadius = 4.0
    badge.isHidden = true
    return badge
  }
  
  func setBadge(visible: Bool, at index: Int) {
    guard badgeViews.indices.contains(index) else { return }
    let badge = badgeViews[index]
    if visible, index == selectedIndex {
      badge.isHidden = true
    } else {
      badge.isHidden = !visible
    }
    if visible {
      badgedIndices.insert(index)
    } else {
      badgedIndices.remove(index)
    }
    updateEdgeIndicators()
  }
  
  static func createEdgeButton() -> UIButton {
    let button = UIButton(type: .custom)
    button.translatesAutoresizingMaskIntoConstraints = false
    button.backgroundColor = .primarySoft
    button.layer.cornerRadius = 11.0
    button.titleLabel?.font = UIFont(name: "PlusJakartaSans-Regular_SemiBold", size: 12.0) ?? UIFont.systemFont(ofSize: 12.0, weight: .semibold)
    button.setTitleColor(.secondaryInverted, for: .normal)
    button.isHidden = true
    return button
  }
  
  @objc
  func didTapLeftIndicator() {
    guard let nextIndex = badgedIndices.filter({ segmentIndex in
      guard let frame = badgeFrameInScrollView(forSegmentAt: segmentIndex) else { return false }
      return frame.minX < scrollView.bounds.minX
    }).max() else { return }
    selectSegment(at: nextIndex, animated: true)
  }
  
  @objc
  func didTapRightIndicator() {
    guard let nextIndex = badgedIndices.filter({ segmentIndex in
      guard let frame = badgeFrameInScrollView(forSegmentAt: segmentIndex) else { return false }
      return frame.maxX > scrollView.bounds.maxX
    }).min() else { return }
    selectSegment(at: nextIndex, animated: true)
  }
  
  private func badgeFrameInScrollView(forSegmentAt index: Int) -> CGRect? {
    guard badgeViews.indices.contains(index) else { return nil }
    return badgeViews[index].convert(badgeViews[index].bounds, to: scrollView)
  }
  
  func updateEdgeIndicators() {
    let offscreen = badgedIndices.filter { segmentIndex in
      guard let frame = badgeFrameInScrollView(forSegmentAt: segmentIndex) else { return false }
      return frame.minX < scrollView.bounds.minX || frame.maxX > scrollView.bounds.maxX
    }
    guard !offscreen.isEmpty else {
      leftEdgeIndicatorButton.isHidden = true
      rightEdgeIndicatorButton.isHidden = true
      return
    }
    
    let leftOff = offscreen.filter { segmentIndex in
      guard let frame = badgeFrameInScrollView(forSegmentAt: segmentIndex) else { return false }
      return frame.minX < scrollView.bounds.minX
    }
    let rightOff = offscreen.filter { segmentIndex in
      guard let frame = badgeFrameInScrollView(forSegmentAt: segmentIndex) else { return false }
      return frame.maxX > scrollView.bounds.maxX
    }
    
    leftEdgeIndicatorButton.isHidden = leftOff.isEmpty
    if !leftOff.isEmpty {
      leftEdgeIndicatorButton.setTitle("\(leftOff.count)", for: .normal)
    }
    
    rightEdgeIndicatorButton.isHidden = rightOff.isEmpty
    if !rightOff.isEmpty {
      rightEdgeIndicatorButton.setTitle("\(rightOff.count)", for: .normal)
    }
  }
}
