//
//  AnAddEditPatientViewController+Helpers.swift
//  A360Scribe
//
//  Created by Mike Grankin on 02.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

internal extension AnAddEditPatientViewController {
  func validateInput() -> Bool {
    guard let firstName = firstNameTextField.text,
          let lastName = lastNameTextField.text,
          let dateOfBirth = dateOfBirthTextField.text,
          !firstName.isEmpty, !lastName.isEmpty, !dateOfBirth.isEmpty
    else {
      let source = firstNameTextField.text.isEmptyOrNil ? firstNameLabel : (lastNameTextField.text.isEmptyOrNil ? lastNameLabel : dateOfBirthLabel)
      let firstResponderAfterProceed = firstNameTextField.text.isEmptyOrNil ? firstNameTextField : (lastNameTextField.text.isEmptyOrNil ? lastNameTextField : dateOfBirthTextField)
      showAlert("First Name, Last Name and Date of Birth are required", source: source, firstResponderAfterProceed: firstResponderAfterProceed)
      return false
    }
    
    guard AnDateFormatter.shared.isValidBirthdate(dateString: dateOfBirth)
    else {
      showAlert("Please enter birthdate in MM/DD/YYYY format between January 1, 1900 and today", source: dateOfBirthLabel, firstResponderAfterProceed: dateOfBirthTextField)
      return false
    }
    
    // Phone: empty or exactly 10 digits
    let phoneDigits = phoneTextField.text?.filter { $0.isNumber } ?? []
    let digitCount = phoneDigits.first == "1" ? phoneDigits.dropFirst().count : phoneDigits.count
    guard digitCount == 0 || digitCount == 10
    else {
      showAlert("Phone number must be exactly 10 digits", source: phoneLabel, firstResponderAfterProceed: phoneTextField)
      return false
    }
    
    // Email: empty or matches simple regex
    let emailText = emailTextField.text ?? ""
    let emailPattern = #"^[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"#
    guard emailText.isEmpty || emailText.range(of: emailPattern, options: .regularExpression) != nil
    else {
      showAlert("Email address has incorrect format", source: emailLabel, firstResponderAfterProceed: emailTextField)
      return false
    }
    
    return true
  }
  
  func makePatientParams(allowDuplicate: Bool) -> AnPatientParams? {
    guard let firstName = firstNameTextField.text,
          let lastName = lastNameTextField.text,
          let birthDate = dateOfBirthTextField.text
    else { return nil }
    
    var params = AnPatientParams(firstName: firstName,
                                 lastName: lastName,
                                 birthDate: birthDate,
                                 middleName: middleNameTextField.text,
                                 title: titleValue,
                                 phone: phoneTextField.text,
                                 email: emailTextField.text,
                                 allowDuplicate: allowDuplicate)
    if isEditMode, let patient {
      params.id = patient.id
      params.genderIdentity = genderIdentityValue
      params.ethnicity = ethnicityValue
      params.occupation = occupationTextField.text
      params.summary = patient.summary
    } 
    return params
  }
  
  func savePatient(allowDuplicate: Bool = false) {
    Task {
      defer {
        saveButton.isEnabled = true
        hideHUD()
      }
      
      guard let params = makePatientParams(allowDuplicate: allowDuplicate) else { return }
      saveButton.isEnabled = false
      do {
        showHUD()
        let result = try await (isEditMode ? patientService.updatePatient(parameters:) : patientService.addPatient(parameters:))(params)
        if isEditMode {
          onPatientUpdated?(result)
        } else {
          onPatientAdded?(result)
        }
      } catch let error {
        if let anError = error as? AnError, anError.statusCode == 409 {
          handleConflict(message: anError.localizedDescription) { [weak self] in
            self?.savePatient(allowDuplicate: true)
          }
        } else {
          showErrorBanner(error.localizedDescription)
        }
      }
    }
  }
  
  func handleConflict(message: String, retryAction: @escaping () -> Void) {
    showAlert(message, title: "Duplicate Patient Detected", proceedTitle: "Proceed", cancelTitle: "Cancel", source: saveButton) {
      retryAction()
    }
  }
  
  func formatDateOfBirth(in textField: UITextField, range: NSRange, replacementString string: String) -> Bool {
    guard let currentText = textField.text, let textRange = Range(range, in: currentText) else { return true }
    if string.rangeOfCharacter(from: CharacterSet.decimalDigits.inverted) != nil { return false }
    let replaced = currentText.replacingCharacters(in: textRange, with: string)
    let digitString = replaced.filter { $0.isNumber }
    // max 8 digits
    guard digitString.count <= 8 else { return false }
    // format with slashes MM/DD/YYYY
    textField.text = formattedDateOfBirth(digits: digitString)
    return false
  }
  
  func formattedDateOfBirth(digits rawDigits: String?) -> String? {
    guard let rawDigits else { return nil }
    let digits = rawDigits.filter { $0.isNumber }
    var result = ""
    for (index, character) in digits.enumerated() {
      // insert slash after 2nd & 4th chars
      if index == 2 || index == 4 { result += "/" }
      result.append(character)
    }
    return result
  }
  
  func formatPhone(in textField: UITextField, range: NSRange, replacementString string: String) -> Bool {
    guard let current = textField.text, let textRange = Range(range, in: current) else { return true }
    // only digits
    if string.rangeOfCharacter(from: CharacterSet.decimalDigits.inverted) != nil { return false }
    let updated = current.replacingCharacters(in: textRange, with: string)
    var digits = updated.filter { $0.isNumber }
    // drop leading “1”
    if digits.first == "1" { digits.removeFirst() }
    // cap at 10 digits
    guard digits.count <= 10 else { return false }
    // build “+1 (AAA) BBB-CCCC”
    var result = "+1"
    if !digits.isEmpty { result += " " }
    switch digits.count {
    case 0...3:
      result += digits
    case 4...6:
      let area = String(digits.prefix(3))
      let mid = String(digits.suffix(from: digits.index(digits.startIndex, offsetBy: 3)))
      result += "(\(area)) \(mid)"
    default:
      let area = String(digits.prefix(3))
      let start = digits.index(digits.startIndex, offsetBy: 3)
      let end = digits.index(digits.startIndex, offsetBy: 6)
      let mid = String(digits[start..<end])
      let last = String(digits.suffix(from: digits.index(digits.startIndex, offsetBy: 6)))
      result += "(\(area)) \(mid)-\(last)"
    }
    textField.text = result
    return false
  }
}
