//
//  AnPatientCell.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SwipeCellKit

final class AnPatientCell: SwipeTableViewCell, Reusable, InterfaceBuilderPrototypable {
  
  // MARK: - Outlets
  
  @IBOutlet private weak var photoImageView: UIImageView!
  @IBOutlet private weak var nameLabel: UILabel!
  @IBOutlet private weak var dobLabel: UILabel!
  @IBOutlet private weak var lastConsultationView: UIView!
  @IBOutlet private weak var lastConsultationIcon: UIImageView!
  @IBOutlet private weak var lastConsultationLabel: UILabel!
  @IBOutlet private weak var buttonsStackView: UIStackView!
  @IBOutlet private weak var startButton: UIButton!
  
  // MARK: - Output
  
  var onProfileTabAction: ((_ patient: AnPatient, _ tab: AnPatientRecordTab) -> Void)?
  var onStartConsultationAction: ((_ patient: AnPatient) -> Void)?
  
  // MARK: - Private Properties
  
  private var patient: AnPatient?
  
  // MARK: - Lifecycle
  
  override func prepareForReuse() {
    super.prepareForReuse()
    nameLabel.text = "Doe, John"
    dobLabel.text = "11/11/1991 (34)"
    photoImageView.image = nil
    lastConsultationView.isHidden = true
    patient = nil
  }
  
  override func awakeFromNib() {
    super.awakeFromNib()
    configureInitialStateUI()
  }
  
  // MARK: - Public functions
  
  func setup(patient: AnPatient) {
    self.patient = patient
    let isActive = patient.isActive ?? false
    nameLabel.text = patient.displayName
    dobLabel.text = patient.formattedBirthDateWithAge
    if let lastConsultationDate = patient.formattedLastConsultationDate {
      lastConsultationLabel.text = lastConsultationDate
      lastConsultationView.isHidden = false
    } else {
      lastConsultationView.isHidden = true
    }
    
    photoImageView.image = UIImage.initialsImage(displayName: patient.displayName,
                                                 diameter: photoImageView.bounds.width,
                                                 backgroundColor: .surfaceSoft,
                                                 borderColor: .secondarySoft,
                                                 borderWidth: 1.0,
                                                 initialsColor: .secondaryStrong)
    backgroundColor = isActive ? .backgroundDefault : .infoBackground
    startButton.configuration?.baseForegroundColor = isActive ? .textPrimary : .secondarySoft
    startButton.applyGlass(isProminent: false)
  }
  
  // MARK: - Actions
  
  @IBAction private func onButtonAction(_ sender: UIButton) {
    guard let patient else { return }
    onStartConsultationAction?(patient)
  }
  
  // MARK: - Private Functions
  
  private func configureInitialStateUI() {
    let isPad = UIDevice.current.isPad
    startButton.isHidden = !isPad
    nameLabel.lastLineFillPercent = isPad ? 20 : 80
    dobLabel.lastLineFillPercent = isPad ? 15 : 70
  }
}
