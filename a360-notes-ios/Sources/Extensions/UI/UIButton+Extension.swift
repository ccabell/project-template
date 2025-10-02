//
//  UIButton+Extension.swift
//  A360Scribe
//
//  Created by Mike Grankin on 20.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

extension UIButton {
  
  // MARK: - Apply Glass Configuration
  
  func applyGlass(isProminent: Bool = false) {
    guard #available(iOS 26.0, *) else { return }
    let currentConfiguration = configuration
    let newConfiguration: UIButton.Configuration = isProminent ? .prominentGlass() : .glass()
    configuration = newConfiguration.withContent(copiedFrom: currentConfiguration)
    setNeedsUpdateConfiguration()
  }
  
  // MARK: - Configure Menus
  
  func configureMenu<T: AnDisplayable>(withOptions options: [T], current: T?, placeholderTitle: String, clearOption: String? = nil, onChange: @escaping (T?) -> Void) {
    configureCommon()
    let initial = current.map { [$0] } ?? []
    menu = makeMenu(withOptions: options, initialSelection: initial, allowsMultipleSelection: false, placeholderTitle: placeholderTitle, clearOption: clearOption, onChangeSingle: onChange)
    updateButtonTitle(forSelected: initial, placeholder: placeholderTitle)
  }
  
  func configureMultiSelectMenu<T: AnDisplayable>(withOptions options: [T], selected: [T], placeholderTitle: String, onChange: @escaping ([T]) -> Void) {
    configureCommon()
    menu = makeMenu(withOptions: options, initialSelection: selected, allowsMultipleSelection: true, placeholderTitle: placeholderTitle, onChangeMulti: onChange)
    updateButtonTitle(forSelected: selected, placeholder: placeholderTitle)
  }
  
  func configureMenuDeferred<T: AnDisplayable>(current: T?, placeholderTitle: String, clearOption: String? = nil, loadOptions: @escaping () async throws -> [T], onChange: @escaping (T?) -> Void) {
    configureCommon()
    let initial = current.map { [$0] } ?? []
    menu = makeDeferredMenu(initialSelection: initial, allowsMultipleSelection: false, placeholderTitle: placeholderTitle, clearOption: clearOption, loadOptions: loadOptions, onChangeSingle: onChange)
    updateButtonTitle(forSelected: initial, placeholder: placeholderTitle)
  }
  
  func configureMenuDeferredMultiSelect<T: AnDisplayable>(selected: [T], placeholderTitle: String, loadOptions: @escaping () async throws -> [T], onChange: @escaping ([T]) -> Void) {
    configureCommon()
    menu = makeDeferredMenu(initialSelection: selected, allowsMultipleSelection: true, placeholderTitle: placeholderTitle, loadOptions: loadOptions, onChangeMulti: onChange)
    updateButtonTitle(forSelected: selected, placeholder: placeholderTitle)
  }
  
  // MARK: - Private Functions
  
  private func makeMenu<T: AnDisplayable>(withOptions options: [T], initialSelection: [T], allowsMultipleSelection: Bool, placeholderTitle: String, clearOption: String? = nil, onChangeSingle: ((T?) -> Void)? = nil, onChangeMulti: (([T]) -> Void)? = nil) -> UIMenu {
    let menuOptionItems: [(group: String?, action: UIAction)] = options.map { option in
      let isSelected = initialSelection.contains(option)
      let action = UIAction(title: option.displayTitle, state: isSelected ? .on : .off) { [weak self] _ in
        guard let self else { return }
        
        var newSelection = initialSelection
        if allowsMultipleSelection {
          if let index = newSelection.firstIndex(of: option) {
            newSelection.remove(at: index)
          } else {
            newSelection.append(option)
          }
          updateButtonTitle(forSelected: newSelection, placeholder: placeholderTitle)
          onChangeMulti?(newSelection)
        } else {
          newSelection = [option]
          updateButtonTitle(forSelected: newSelection, placeholder: placeholderTitle)
          onChangeSingle?(option)
        }
        
        menu = makeMenu(withOptions: options, initialSelection: newSelection, allowsMultipleSelection: allowsMultipleSelection, placeholderTitle: placeholderTitle, clearOption: clearOption, onChangeSingle: onChangeSingle, onChangeMulti: onChangeMulti)
      }
      if allowsMultipleSelection { action.attributes = [.keepsMenuPresented] }
      return (option.groupTitle, action)
    }
    
    var elements: [UIMenuElement] = []
    
    if let clearOption, !allowsMultipleSelection {
      let clearState: UIMenuElement.State = initialSelection.isEmpty ? .on : .off
      let clear = UIAction(title: clearOption, state: clearState) { [weak self] _ in
        guard let self else { return }
        onChangeSingle?(nil)
        let emptySelection: [T] = []
        updateButtonTitle(forSelected: emptySelection, placeholder: placeholderTitle)
        menu = makeMenu(withOptions: options, initialSelection: [], allowsMultipleSelection: false, placeholderTitle: placeholderTitle, clearOption: clearOption, onChangeSingle: onChangeSingle)
      }
      elements.append(clear)
    }
    
    let hasGroups = menuOptionItems.contains { $0.group != nil }
    if hasGroups {
      let groupTitles = options.uniqued(by: \.groupTitle).compactMap(\.groupTitle)
      
      for groupTitle in groupTitles {
        let children = menuOptionItems.filter { $0.group == groupTitle }.map { $0.action }
        elements.append(UIMenu(title: groupTitle, options: .displayInline, children: children))
      }
      
      let ungrouped = menuOptionItems.filter { $0.group == nil }.map { $0.action }
      elements.append(contentsOf: ungrouped)
      
      return UIMenu(title: placeholderTitle, children: elements)
    } else {
      elements.append(contentsOf: menuOptionItems.map { $0.action })
      return UIMenu(title: placeholderTitle, children: elements)
    }
  }
  
  private func makeDeferredMenu<T: AnDisplayable>(initialSelection: [T], allowsMultipleSelection: Bool, placeholderTitle: String, clearOption: String? = nil, loadOptions: @escaping () async throws -> [T], onChangeSingle: ((T?) -> Void)? = nil, onChangeMulti: (([T]) -> Void)? = nil) -> UIMenu {
    let deferred = UIDeferredMenuElement { [weak self] completion in
      guard let self else {
        completion([])
        return
      }
      
      Task {
        do {
          let options = try await loadOptions()
          var initial = initialSelection
          var infoAction: UIAction?
          
          if allowsMultipleSelection {
            let filtered = initial.filter { options.contains($0) }
            if filtered.count != initial.count {
              let removed = initial.filter { !options.contains($0) }
              let removedList = removed.map { $0.displayTitle }.joined(separator: ", ")
              infoAction = UIAction(title: "Selection updated", subtitle: removed.isEmpty ? "" : "Removed: \(removedList)", attributes: [.disabled]) { _ in }
              initial = filtered
              onChangeMulti?(filtered)
            }
          } else if let only = initial.first, !options.contains(only) {
            onChangeSingle?(nil)
            initial = []
            infoAction = UIAction(title: "Selection cleared", subtitle: "Previously selected: \(only.displayTitle) - unavailable", attributes: [.disabled]) { _ in }
          }
          
          let baseMenu = self.makeMenu(withOptions: options, initialSelection: initial, allowsMultipleSelection: allowsMultipleSelection, placeholderTitle: placeholderTitle, clearOption: clearOption, onChangeSingle: onChangeSingle, onChangeMulti: onChangeMulti)
          
          let children = baseMenu.children + (infoAction.map { [$0] } ?? [])
          let finalMenu = baseMenu.replacingChildren(baseMenu.children + (infoAction.map { [$0] } ?? []))
          
          self.menu = finalMenu
          self.updateButtonTitle(forSelected: initial, placeholder: placeholderTitle)
          completion(children)
        } catch {
          Task { @MainActor in
            await Task.yield()
            self.menu = nil
            self.menu = self.makeDeferredMenu(initialSelection: initialSelection, allowsMultipleSelection: allowsMultipleSelection, placeholderTitle: placeholderTitle, clearOption: clearOption, loadOptions: loadOptions, onChangeSingle: onChangeSingle, onChangeMulti: onChangeMulti)
          }
        }
      }
    }
    
    let defaultTitle: String
    if allowsMultipleSelection {
      defaultTitle = initialSelection.isEmpty ? placeholderTitle : initialSelection.map { $0.displayTitle }.joined(separator: ", ")
    } else {
      defaultTitle = initialSelection.first?.displayTitle ?? clearOption ?? placeholderTitle
    }
    let defaultSelected = UIAction(title: defaultTitle, attributes: [.disabled], state: .on) { _ in }
    return UIMenu(title: placeholderTitle, children: [defaultSelected, deferred])
  }
  
  // MARK: - Private: Common
  
  private func configureCommon() {
    showsMenuAsPrimaryAction = true
    configuration?.indicator = .popup
    configuration?.titleLineBreakMode = .byTruncatingTail
    changesSelectionAsPrimaryAction = false
  }
  
  private func updateButtonTitle<T: AnDisplayable>(forSelected items: [T], placeholder: String?) {
    let titles = items.map {
      guard let groupTitle = $0.groupTitle, !groupTitle.isEmpty else { return $0.displayTitle }
      return "\(groupTitle): \($0.displayTitle)"
    }
    configuration?.title = titles.isEmpty ? placeholder : titles.joined(separator: ", ")
  }
}

extension UIButton.Configuration {
  func withContent(copiedFrom source: UIButton.Configuration?) -> UIButton.Configuration {
    guard let source else { return self }
    var merged = self

    // Titles
    merged.title = source.title
    merged.subtitle = source.subtitle
    merged.attributedTitle = source.attributedTitle
    merged.attributedSubtitle = source.attributedSubtitle
    merged.titleAlignment = source.titleAlignment
    merged.titlePadding = source.titlePadding
    merged.titleTextAttributesTransformer = source.titleTextAttributesTransformer
    merged.subtitleTextAttributesTransformer = source.subtitleTextAttributesTransformer

    // Image
    merged.image = source.image
    merged.imagePlacement = source.imagePlacement
    merged.imagePadding = source.imagePadding
    merged.imageColorTransformer = source.imageColorTransformer
    merged.preferredSymbolConfigurationForImage = source.preferredSymbolConfigurationForImage

    // Layout & sizing
    merged.contentInsets = source.contentInsets
    merged.buttonSize = source.buttonSize

    // Colors
    merged.baseForegroundColor = source.baseForegroundColor
    merged.baseBackgroundColor = source.baseBackgroundColor

    // Activity indicator
    merged.showsActivityIndicator = source.showsActivityIndicator

    // Intentionally NOT copying:
    // - merged.background
    // - merged.cornerStyle
    // to retain the visual effect and corners of the new base style.

    return merged
  }
}
