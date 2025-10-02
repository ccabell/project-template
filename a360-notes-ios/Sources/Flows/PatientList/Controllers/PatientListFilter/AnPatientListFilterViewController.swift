//
//  AnPatientListFilterViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnPatientListFilterOutput {
  var onApply: ((AnPatientListFilter) -> Void)? { get set }
  var onDismiss: (() -> Void)? { get set }
  var filter: AnPatientListFilter { get set }
}

final class AnPatientListFilterViewController: AnBaseViewController, AnPatientListFilterOutput {
  
  // MARK: - Output
  
  var onApply: ((AnPatientListFilter) -> Void)?
  var onDismiss: (() -> Void)?
  var filter = AnPatientListFilter()
  
  // MARK: - Outlets
  
  @IBOutlet internal weak var clearButton: UIBarButtonItem!
  @IBOutlet internal weak var applyButton: UIBarButtonItem!
  @IBOutlet internal weak var orderByButton: UIButton!
  @IBOutlet internal weak var ageLabel: UILabel!
  @IBOutlet internal weak var ageFromTextField: UITextField!
  @IBOutlet internal weak var ageToTextField: UITextField!
  @IBOutlet internal weak var lastConsultationLabel: UILabel!
  @IBOutlet internal weak var lastConsultationFromTextField: UITextField!
  @IBOutlet internal weak var lastConsultationToTextField: UITextField!
  @IBOutlet internal weak var statusButton: UIButton!
  
  // MARK: - Private Properties
  
  internal var isUpdated = false {
    didSet {
      applyButton.isEnabled = true
      clearButton.isEnabled = true
    }
  }
  
  internal lazy var fromCalendarSelection = UICalendarSelectionSingleDate(delegate: self)
  internal lazy var toCalendarSelection = UICalendarSelectionSingleDate(delegate: self)
  internal lazy var fromCalendarView = makeCalendarView(with: fromCalendarSelection)
  internal lazy var toCalendarView = makeCalendarView(with: toCalendarSelection)
  
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
    filter = AnPatientListFilter()
    ageFromTextField.text = nil
    ageToTextField.text = nil
    lastConsultationFromTextField.text = nil
    lastConsultationToTextField.text = nil
    fromCalendarSelection.selectedDate = nil
    toCalendarSelection.selectedDate = nil
    configureUI()
  }
  
  @IBAction private func onApplyAction(_ sender: Any) {
    view.endEditing(true)
    guard validateInput() else { return }
    fillFilterValues()
    onApply?(filter)
  }
  
  // MARK: - Private Functions
  
  private func configureNavigationBar() {
    navigationController?.navigationBar.configureAppearance(backgroundColor: .backgroundDefault, removeShadow: false)
  }
  
  private func configureUI() {
    if let ageFrom = filter.ageFrom {
      ageFromTextField.text = String(ageFrom)
    }
    
    if let ageTo = filter.ageTo {
      ageToTextField.text = String(ageTo)
    }
    
    if let lastConsultationFromDate = filter.lastConsultationFrom {
      lastConsultationFromTextField.text = AnDateFormatter.shared.convert(date: lastConsultationFromDate, to: .americanDate)
    }
    
    if let lastConsultationToDate = filter.lastConsultationTo {
      lastConsultationToTextField.text = AnDateFormatter.shared.convert(date: lastConsultationToDate, to: .americanDate)
    }
    
    configureAllPickers()
    clearButton.isEnabled = !filter.isFilterEmpty
  }
  
  private func validateInput() -> Bool {
    if let ageFromText = ageFromTextField.text, !ageFromText.isEmpty, Int(ageFromText) == nil {
      showAlert("Age \"From\" must be a valid number", source: ageLabel, firstResponderAfterProceed: ageFromTextField)
      return false
    }
    
    if let ageToText = ageToTextField.text, !ageToText.isEmpty, Int(ageToText) == nil {
      showAlert("Age \"To\" must be a valid number", source: ageLabel, firstResponderAfterProceed: ageToTextField)
      return false
    }
    
    if let ageFromText = ageFromTextField.text,
       let ageToText = ageToTextField.text,
       let fromAge = Int(ageFromText),
       let toAge = Int(ageToText),
       fromAge > toAge {
      showAlert("Age \"From\" must be less than or equal to \"To\"", source: ageLabel)
      return false
    }
    
    if let lastConsultationFromText = lastConsultationFromTextField.text, !lastConsultationFromText.isEmpty,
       AnDateFormatter.shared.convert(dateString: lastConsultationFromText, from: .americanDate) == nil {
      showAlert("\"Last Visit From\" date must be valid", source: lastConsultationLabel, firstResponderAfterProceed: lastConsultationFromTextField)
      return false
    }
    
    if let lastConsultationToText = lastConsultationToTextField.text, !lastConsultationToText.isEmpty,
       AnDateFormatter.shared.convert(dateString: lastConsultationToText, from: .americanDate) == nil {
      showAlert("\"Last Visit To\" date must be valid", source: lastConsultationLabel, firstResponderAfterProceed: lastConsultationToTextField)
      return false
    }
    
    if let lastConsultationFromText = lastConsultationFromTextField.text,
       let lastConsultationToText = lastConsultationToTextField.text,
       let lastConsultationFromDate = AnDateFormatter.shared.convert(dateString: lastConsultationFromText, from: .americanDate),
       let lastConsultationToDate = AnDateFormatter.shared.convert(dateString: lastConsultationToText, from: .americanDate),
       lastConsultationFromDate > lastConsultationToDate {
      showAlert("Last Visit \"From\" date must be earlier than or equal to \"To\" date", source: lastConsultationLabel)
      return false
    }
    return true
  }
  
  private func fillFilterValues() {
    var ageFromValue: Int?
    if let text = ageFromTextField.text, !text.isEmpty {
      ageFromValue = Int(text)
    }
    
    var ageToValue: Int?
    if let text = ageToTextField.text, !text.isEmpty {
      ageToValue = Int(text)
    }
    
    var lastConsultationFrom: Date?
    if let dateComponents = fromCalendarSelection.selectedDate {
      lastConsultationFrom = Calendar.current.date(from: dateComponents)
    }
    
    var lastConsultationTo: Date?
    if let dateComponents = toCalendarSelection.selectedDate {
      lastConsultationTo = Calendar.current.date(from: dateComponents)
    }
    
    filter = AnPatientListFilter(orderBy: filter.orderBy,
                                 ageFrom: ageFromValue,
                                 ageTo: ageToValue,
                                 lastConsultationFrom: lastConsultationFrom,
                                 lastConsultationTo: lastConsultationTo,
                                 status: filter.status)
  }
}
