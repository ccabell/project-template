//
//  AnConsultationListFilterViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 15.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnConsultationListFilterOutput {
  var onApply: ((AnConsultationListFilter) -> Void)? { get set }
  var onDismiss: (() -> Void)? { get set }
  var filter: AnConsultationListFilter { get set }
}

final class AnConsultationListFilterViewController: AnBaseViewController, AnConsultationListFilterOutput {
  
  // MARK: - Output
  
  var onApply: ((AnConsultationListFilter) -> Void)?
  var onDismiss: (() -> Void)?
  var filter = AnConsultationListFilter()
  
  // MARK: - Outlets
  
  @IBOutlet private weak var clearButton: UIBarButtonItem!
  @IBOutlet private weak var applyButton: UIBarButtonItem!
  @IBOutlet private weak var orderByButton: UIButton!
  @IBOutlet private weak var statusButton: UIButton!
  @IBOutlet private weak var workflowButton: UIButton!
  @IBOutlet private weak var expertButton: UIButton!
  
  // MARK: - Private Properties
  
  private lazy var practiceService: AnPracticeService = AnAPIService()
  private var isUpdated = false {
    didSet {
      applyButton.isEnabled = true
      clearButton.isEnabled = true
    }
  }
  private var workflows: [AnWorkflow] = []
  private var experts: [AnExpert] = []
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureNavigationBar()
    configureUI()
  }
  
  // MARK: - Actions
  
  @IBAction private func onCancelAction(_ sender: Any) {
    view.endEditing(true)
    onDismiss?()
  }
  
  @IBAction private func onClearAction(_ sender: Any) {
    view.endEditing(true)
    isUpdated = true
    filter = AnConsultationListFilter()
    configureUI()
  }
  
  @IBAction private func onApplyAction(_ sender: Any) {
    view.endEditing(true)
    onApply?(filter)
  }
  
  // MARK: - Private Functions
  
  private func configureNavigationBar() {
    navigationController?.navigationBar.configureAppearance(backgroundColor: .backgroundDefault, removeShadow: false)
  }
  
  private func configureUI() {
    configureButtonsMenu()
    clearButton.isEnabled = !filter.isFilterEmpty
  }
  
  private func configureButtonsMenu() {
    orderByButton.configureMenu(withOptions: AnConsultationListFilter.OrderBy.allCases, current: filter.orderBy, placeholderTitle: "Sort By") { [weak self] newValue in
      guard let self, let newValue else { return }
      isUpdated = true
      filter.orderBy = newValue
    }

    statusButton.configureMultiSelectMenu(withOptions: AnConsultationStatus.allCases, selected: filter.statuses, placeholderTitle: "Select statuses") { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      filter.statuses = newValue
    }
    
    workflowButton.configureMenuDeferred(current: filter.workflow, placeholderTitle: "Select workflow", clearOption: "All", loadOptions: { [weak self] in
      guard let self else { return [] }
      if workflows.isEmpty {
        do {
          let fetched: [AnWorkflow] = try await practiceService.getWorkflows()
          workflows = fetched
        } catch {
          showErrorBanner("Failed to load workflows", subtitle: error.localizedDescription)
          throw error
        }
      }
      return workflows
    }, onChange: { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      filter.workflow = newValue
    })
    
    expertButton.configureMenuDeferred(current: filter.expert, placeholderTitle: "Select expert", clearOption: "All", loadOptions: { [weak self] in
      guard let self else { return [] }
      if experts.isEmpty {
        do {
          let fetched: [AnExpert] = try await practiceService.getExperts()
          experts = fetched
        } catch {
          showErrorBanner("Failed to load experts", subtitle: error.localizedDescription)
          throw error
        }
      }
      return experts
    }, onChange: { [weak self] newValue in
      guard let self else { return }
      isUpdated = true
      filter.expert = newValue
    })
  }
}
