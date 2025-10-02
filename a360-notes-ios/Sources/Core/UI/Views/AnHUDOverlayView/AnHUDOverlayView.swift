//
//  AnHUDOverlayView.swift
//  A360Scribe
//
//  Created by Mike Grankin on 26.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

@MainActor
final class AnHUDOverlayView: UIView {
  
  // MARK: - Public Functions
  
  @discardableResult
  static func show(in parent: UIView, blocksTouches: Bool = true) -> AnHUDOverlayView {
    let hud = AnHUDOverlayView(blurStyle: .light, blocksTouches: blocksTouches, outerSize: 120.0, innerSize: 52.0)
    parent.addSubview(hud)
    NSLayoutConstraint.activate([hud.topAnchor.constraint(equalTo: parent.topAnchor),
                                 hud.leadingAnchor.constraint(equalTo: parent.leadingAnchor),
                                 hud.trailingAnchor.constraint(equalTo: parent.trailingAnchor),
                                 hud.bottomAnchor.constraint(equalTo: parent.bottomAnchor)])
    hud.present()
    return hud
  }
  
  func hide(completion: (() -> Void)? = nil) {
    stopSpinning()
    UIView.animate(withDuration: fadeDuration) {
      self.alpha = 0.0
    } completion: { _ in
      self.removeFromSuperview()
      completion?()
    }
  }
  
  // MARK: - Private properties
  
  private let backgroundBlurView: UIVisualEffectView
  private let spinnerImageView: UIImageView
  private let centerImageView: UIImageView
  private let outerSize: CGFloat
  private let innerSize: CGFloat
  
  let fadeDuration: TimeInterval = 0.22
  let rotationDuration = 1.25
  let rotationKey = "an.rotation"
  
  // MARK: - Lifecycle
  
  private init(blurStyle: UIBlurEffect.Style, blocksTouches: Bool, outerSize: CGFloat, innerSize: CGFloat) {
    backgroundBlurView = UIVisualEffectView(effect: UIBlurEffect(style: blurStyle))
    spinnerImageView = UIImageView(image: UIImage(named: "a360_loader_arrow") ?? UIImage())
    centerImageView = UIImageView(image: UIImage(named: "a360_loader_logo") ?? UIImage())
    self.outerSize = outerSize
    self.innerSize = innerSize
    
    super.init(frame: .zero)
    
    isUserInteractionEnabled = blocksTouches
    translatesAutoresizingMaskIntoConstraints = false
    
    setupLayout()
    startSpinning()
  }
  
  required init?(coder: NSCoder) {
    fatalError("init(coder:) has not been implemented")
  }
  
  // MARK: - Private Functions
  
  private func setupLayout() {
    backgroundBlurView.translatesAutoresizingMaskIntoConstraints = false
    addSubview(backgroundBlurView)
    NSLayoutConstraint.activate([backgroundBlurView.topAnchor.constraint(equalTo: topAnchor),
                                 backgroundBlurView.leadingAnchor.constraint(equalTo: leadingAnchor),
                                 backgroundBlurView.trailingAnchor.constraint(equalTo: trailingAnchor),
                                 backgroundBlurView.bottomAnchor.constraint(equalTo: bottomAnchor)])
    
    let content = UIView(frame: .zero)
    content.translatesAutoresizingMaskIntoConstraints = false
    addSubview(content)
    NSLayoutConstraint.activate([content.centerXAnchor.constraint(equalTo: centerXAnchor),
                                 content.centerYAnchor.constraint(equalTo: centerYAnchor)])
    
    spinnerImageView.translatesAutoresizingMaskIntoConstraints = false
    spinnerImageView.contentMode = .scaleAspectFit
    content.addSubview(spinnerImageView)
    
    centerImageView.translatesAutoresizingMaskIntoConstraints = false
    centerImageView.contentMode = .scaleAspectFit
    content.addSubview(centerImageView)
    
    NSLayoutConstraint.activate([spinnerImageView.centerXAnchor.constraint(equalTo: content.centerXAnchor),
                                 spinnerImageView.centerYAnchor.constraint(equalTo: content.centerYAnchor),
                                 spinnerImageView.widthAnchor.constraint(equalToConstant: outerSize),
                                 spinnerImageView.heightAnchor.constraint(equalToConstant: outerSize),
                                 centerImageView.centerXAnchor.constraint(equalTo: content.centerXAnchor),
                                 centerImageView.centerYAnchor.constraint(equalTo: content.centerYAnchor),
                                 centerImageView.widthAnchor.constraint(equalToConstant: innerSize),
                                 centerImageView.heightAnchor.constraint(equalToConstant: innerSize)])
  }
  
  private func startSpinning() {
    let rotation = CABasicAnimation(keyPath: "transform.rotation.z")
    rotation.fromValue = 0.0
    rotation.toValue = Double.pi * 2.0
    rotation.duration = rotationDuration
    rotation.repeatCount = .infinity
    rotation.isRemovedOnCompletion = false
    rotation.timingFunction = CAMediaTimingFunction(name: .linear)
    spinnerImageView.layer.add(rotation, forKey: rotationKey)
  }
  
  private func stopSpinning() {
    let layer = spinnerImageView.layer
    CATransaction.begin()
    CATransaction.setDisableActions(true)
    if let presentation = layer.presentation() {
      layer.transform = presentation.transform
    }
    layer.removeAnimation(forKey: rotationKey)
    CATransaction.commit()
  }
  
  private func present() {
    alpha = 0.0
    UIView.animate(withDuration: fadeDuration) {
      self.alpha = 1.0
    }
  }
}
