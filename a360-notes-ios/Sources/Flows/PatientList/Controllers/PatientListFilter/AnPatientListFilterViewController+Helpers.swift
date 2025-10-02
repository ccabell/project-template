//
//  AnPatientListFilterViewController+Helpers.swift
//  A360Scribe
//
//  Created by Mike Grankin on 09.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

internal extension AnPatientListFilterViewController {
  func makeCalendarView(with selection: UICalendarSelectionSingleDate) -> UICalendarView {
    let calendar = UICalendarView()
    calendar.translatesAutoresizingMaskIntoConstraints = false
    calendar.selectionBehavior = selection
    calendar.availableDateRange = .init(start: .minAvailableDate, end: .now)
    return calendar
  }
  
  func configureAllPickers() {
    configureButtonsMenu()
    configureCalendarPickers()
  }
  
  private func configureButtonsMenu() {
    orderByButton.configureMenu(withOptions: AnPatientListFilter.OrderBy.allCases, current: filter.orderBy, placeholderTitle: "Sort By") { [weak self] newValue in
      guard let self, let newValue else { return }
      isUpdated = true
      filter.orderBy = newValue
    }
    
    statusButton.configureMenu(withOptions: AnPatientStatus.allCases, current: filter.status, placeholderTitle: "Patient status") { [weak self] newValue in
      guard let self, let newValue else { return }
      isUpdated = true
      filter.status = newValue
    }
  }
  
  private func configureCalendarPickers() {
    configureCalendar(fromCalendarView, for: lastConsultationFromTextField)
    configureCalendar(toCalendarView, for: lastConsultationToTextField)
  }
  
  private func configureCalendar(_ calendar: UICalendarView, for textField: UITextField) {
    textField.inputView = calendar
    textField.delegate = self
    
    if let current = textField.text, !current.isEmpty,
       let date = AnDateFormatter.shared.convert(dateString: current, from: .americanDate) {
      let comps = Calendar.current.dateComponents([.year, .month, .day], from: date)
      (calendar.selectionBehavior as? UICalendarSelectionSingleDate)?.setSelected(comps, animated: false)
    }
  }
}

// MARK: - UITextFieldDelegate

extension AnPatientListFilterViewController: UITextFieldDelegate {
  func textFieldDidBeginEditing(_ textField: UITextField) {
    isUpdated = true
  }
  
  func textFieldShouldClear(_ textField: UITextField) -> Bool {
    isUpdated = true
    if textField == lastConsultationFromTextField {
      fromCalendarSelection.setSelected(nil, animated: false)
    } else if textField == lastConsultationToTextField {
      toCalendarSelection.setSelected(nil, animated: false)
    }
    return true
  }
}

extension AnPatientListFilterViewController: UICalendarSelectionSingleDateDelegate {
  func dateSelection(_ selection: UICalendarSelectionSingleDate, didSelectDate dateComponents: DateComponents?) {
    isUpdated = true
    guard let dateComponents, let date = Calendar.current.date(from: dateComponents) else { return }
    
    let formatted = AnDateFormatter.shared.convert(date: date, to: .americanDate)
    if selection == fromCalendarSelection {
      lastConsultationFromTextField.text = formatted
    } else if selection == toCalendarSelection {
      lastConsultationToTextField.text = formatted
    }
    view.endEditing(true)
  }
}
