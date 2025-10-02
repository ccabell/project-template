//
//  AnConsultationCell.swift
//  A360Scribe
//
//  Created by Mike Grankin on 13.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SwipeCellKit

final class AnConsultationCell: SwipeTableViewCell, Reusable, InterfaceBuilderPrototypable {
  
  // MARK: - Outlets
  
  @IBOutlet private weak var workflowLabel: UILabel!
  @IBOutlet private weak var expertLabel: UILabel!
  @IBOutlet private weak var dateLabel: UILabel!
  @IBOutlet private weak var statusLabel: UILabel!
  
  // MARK: - Public Properties

  var prohibitedActionSource: UIView? {
    switch consultation?.prohibitedActionMessage {
    case .notIdle:
      return statusLabel
    case .anotherExpert:
      return expertLabel
    case .none:
      return nil
    }
  }
  
  // MARK: - Private Properties
  
  private var consultation: AnConsultation?
  
  // MARK: - Lifecycle
  
  override func prepareForReuse() {
    super.prepareForReuse()
    workflowLabel.text = "Consultation"
    expertLabel.text = "John Doe"
    dateLabel.text = "01/01/2025 11:00 AM - 11:30 AM"
    statusLabel.text = "On-Going"
    statusLabel.borderWidth = 0.0
    consultation = nil
  }
  
  // MARK: - Public functions
  
  func setup(consultation: AnConsultation) {
    self.consultation = consultation
    workflowLabel.text = consultation.workflow?.name
    expertLabel.text = consultation.expert.displayTitle
    if let startedAt = consultation.startedAt {
      let startedString = AnDateFormatter.shared.convert(date: startedAt, to: .shortAmericanDateTime)
      if let finishedAt = consultation.finishedAt {
        let finishedString = AnDateFormatter.shared.convert(date: finishedAt, to: .americanTime)
        dateLabel.text = "\(startedString) - \(finishedString)"
      } else {
        dateLabel.text = startedString
      }
    } else {
      dateLabel.text = nil
    }
    statusLabel.text = consultation.status.displayTitle
    statusLabel.backgroundColor = consultation.status.backgroundColor
    statusLabel.textColor = consultation.status.foregroundColor
    statusLabel.borderColor = consultation.status.foregroundColor
    statusLabel.borderWidth = 1.0
  }
}
