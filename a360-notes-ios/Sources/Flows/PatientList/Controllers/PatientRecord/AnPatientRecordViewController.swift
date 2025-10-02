//
//  AnPatientRecordViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 16.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

enum AnPatientRecordTab: String {
  case history = "History"
  case summary = "Summary"
  case profile = "Profile"
}

protocol AnPatientRecordOutput {
  var onStartConsultation: ((AnPatient) -> Void)? { get set }
  var onResumeConsultation: ((AnPatient, AnConsultation) -> Void)? { get set }
  var onShowConsultationProfile: ((AnPatient, AnConsultation) -> Void)? { get set }
  var onEditPatient: ((AnPatient) -> Void)? { get set }
  var onEditPatientSummary: ((AnPatient) -> Void)? { get set }
  var onClose: (() -> Void)? { get set }
  var patient: AnPatient? { get set }
  var activeTab: AnPatientRecordTab { get set }
  var onShowConsultationListFilter: ((AnConsultationListFilter) -> Void)? { get set }
  var consultationListFilter: AnConsultationListFilter { get set }
}

final class AnPatientRecordViewController: AnBaseViewController, AnPatientRecordOutput {
  
  // MARK: - Output
  
  var onStartConsultation: ((AnPatient) -> Void)?
  var onResumeConsultation: ((AnPatient, AnConsultation) -> Void)?
  var onShowConsultationProfile: ((AnPatient, AnConsultation) -> Void)?
  var onEditPatient: ((AnPatient) -> Void)?
  var onEditPatientSummary: ((AnPatient) -> Void)?
  var onClose: (() -> Void)?
  var patient: AnPatient?
  var activeTab: AnPatientRecordTab = .history
  var onShowConsultationListFilter: ((AnConsultationListFilter) -> Void)?
  var consultationListFilter = AnConsultationListFilter() {
    didSet {
      guard selectedTab == .history else { return }
      refreshData()
    }
  }
  
  // MARK: - Outlets

  @IBOutlet private weak var moreBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var startConsultationBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var segmentedControl: AnSegmentedControl!
  @IBOutlet private weak var profileContainer: UIView!
  @IBOutlet private weak var photoImageView: UIImageView!
  @IBOutlet private weak var firstNameView: UIView!
  @IBOutlet private weak var firstNameLabel: UILabel!
  @IBOutlet private weak var middleNameView: UIView!
  @IBOutlet private weak var middleNameLabel: UILabel!
  @IBOutlet private weak var lastNameView: UIView!
  @IBOutlet private weak var lastNameLabel: UILabel!
  @IBOutlet private weak var dateOfBirthView: UIView!
  @IBOutlet private weak var dateOfBirthLabel: UILabel!
  @IBOutlet private weak var titleView: UIView!
  @IBOutlet private weak var titleLabel: UILabel!
  @IBOutlet private weak var genderView: UIView!
  @IBOutlet private weak var genderLabel: UILabel!
  @IBOutlet private weak var ethnicityView: UIView!
  @IBOutlet private weak var ethnicityLabel: UILabel!
  @IBOutlet private weak var occupationView: UIView!
  @IBOutlet private weak var occupationLabel: UILabel!
  @IBOutlet private weak var phoneView: UIView!
  @IBOutlet private weak var phoneLabel: UILabel!
  @IBOutlet private weak var emailView: UIView!
  @IBOutlet private weak var emailLabel: UILabel!
  @IBOutlet private var patientProfileViews: [UIView]!
  @IBOutlet private weak var patientSummaryView: UIView!
  @IBOutlet private weak var patientSummaryLabel: UILabel!
  @IBOutlet internal weak var consultationListView: UIView!
  @IBOutlet internal weak var consultationListSearchBar: UISearchBar!
  @IBOutlet internal weak var consultationListFilterButton: UIButton!
  @IBOutlet internal weak var consultationListTableView: UITableView!
  
  // MARK: - Private Properties
  
  internal lazy var patientService: AnPatientService = AnAPIService()
  internal lazy var consultationService: AnConsultationService = AnAPIService()
  private var selectedTab: AnPatientRecordTab {
    guard let currentSegmentDetails = segmentedControl.currentSegmentDetails,
          let currentTab = AnPatientRecordTab(rawValue: currentSegmentDetails.title) else {
      return .history
    }
    return currentTab
  }
  
  internal var consultations: [AnConsultation] = []
  internal var currentPagination = AnPagination()
  internal var isFetching = false
  internal var searchDebounceTask: Task<Void, Never>?
  internal var activeSearchTask: Task<Void, Never>?
  internal var dataState: AnDataState = .noData {
    didSet {
      Task {
        updateDataUI(dataState)
      }
    }
  }
  internal var hasAnimatedFirstCell: Bool = false
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    segmentedControl.selectSegment(withTitle: activeTab.rawValue, force: true)
    configureUI()
    configureConsultationsTableView()
    loadPatient()
    configureButtonsMenu()
  }
  
  // MARK: - Public Functions
  
  func activateTab(_ activeTab: AnPatientRecordTab) {
    segmentedControl.selectSegment(withTitle: activeTab.rawValue, force: true)
  }
  
  func refresh(patient updatedPatient: AnPatient) {
    patient = updatedPatient
    configureUI()
  }
  
  func refresh(consultation updatedConsultation: AnConsultation) {
    guard let index = consultations.firstIndex(where: { $0.id == updatedConsultation.id }) else { return }
    consultations[index] = updatedConsultation
    consultationListTableView.reloadRows(at: [IndexPath(row: index, section: 0)], with: .automatic)
  }
  
  // MARK: - Actions
  
  @IBAction private func onStartConsultationAction(_ sender: Any) {
    guard let patient else { return }
    guard patient.isActive ?? false else {
      showInactivePatientAlert()
      return
    }
    onStartConsultation?(patient)
  }
  
  @IBAction private func onBackAction(_ sender: Any) {
    onClose?()
  }
  
  @IBAction private func onSegmentedControlValueChanged(_ sender: AnSegmentedControl) {
    switch selectedTab {
    case .profile, .summary:
      profileContainer.isHidden = false
      consultationListView.isHidden = true
      moreBarButtonItem.isHidden = false
      configureProfile()
      configureSummary()
    case .history:
      profileContainer.isHidden = true
      consultationListView.isHidden = false
      moreBarButtonItem.isHidden = true
      refreshData()
    }
  }
  
  @IBAction private func onShowConsultationListFilterAction(_ sender: Any) {
    consultationListSearchBar.resignFirstResponder()
    onShowConsultationListFilter?(consultationListFilter)
  }
  
  // MARK: - Private Functions
  
  private func loadPatient() {
    Task {
      
      defer {
        hideHUD()
      }
      
      guard let patientId = patient?.id else { return }
      do {
        showHUD(in: profileContainer)
        let patientProfile: AnPatient = try await patientService.getPatient(patientId)
        patient = patientProfile
        configureUI()
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
  
  private func configureButtonsMenu() {
    let editAction = UIAction(title: "Edit", image: UIImage(systemName: "pencil.and.list.clipboard")) { [weak self] _ in
      guard let self, let patient else { return }
      switch selectedTab {
      case .profile:
        onEditPatient?(patient)
      case .summary:
        onEditPatientSummary?(patient)
      case .history:
        break
      }
    }
  
    let menu = UIMenu(title: "", children: [editAction])
    moreBarButtonItem.menu = menu
  }
  
  private func configureUI() {
    configureBasicUI()
    configureProfile()
    configureSummary()
  }
  
  private func configureBasicUI() {
    guard let patient else { return }
    
    consultationListFilterButton.applyGlass(isProminent: true)
    setNavigationTitle(patient.displayName, subtitle: patient.formattedBirthDateWithAge)
    photoImageView.image = UIImage.initialsImage(displayName: patient.displayName,
                                                 diameter: photoImageView.bounds.width,
                                                 backgroundColor: .surfaceSoft,
                                                 borderColor: .secondarySoft,
                                                 borderWidth: 1.0,
                                                 initialsColor: .secondaryStrong)
  }
  
  private func configureProfile() {
    guard let patient, selectedTab == .profile else {
      for view in patientProfileViews {
        view.isHidden = true
      }
      return
    }
    
    configureBasicUI()
    
    firstNameView.isHidden = false
    firstNameLabel.text = patient.firstName
    middleNameView.isHidden = patient.middleName.isEmptyOrNil
    middleNameLabel.text = patient.middleName
    lastNameView.isHidden = false
    lastNameLabel.text = patient.lastName
    dateOfBirthView.isHidden = false
    let formattedBirthDate = AnDateFormatter.shared.convert(dateString: patient.birthDate, from: .serverDate, to: .americanDate)
    dateOfBirthLabel.text = formattedBirthDate
    titleView.isHidden = patient.title == nil
    titleLabel.text = patient.title?.displayTitle
    genderView.isHidden = patient.genderIdentity == nil
    genderLabel.text = patient.genderIdentity?.displayTitle
    ethnicityView.isHidden = patient.ethnicity == nil
    ethnicityLabel.text = patient.ethnicity?.displayTitle
    occupationView.isHidden = patient.occupation == nil
    occupationLabel.text = patient.occupation
    phoneView.isHidden = patient.phone.isEmptyOrNil
    phoneLabel.text = patient.phone
    emailView.isHidden = patient.email.isEmptyOrNil
    emailLabel.text = patient.email
  }
  
  private func configureSummary() {
    guard let patient, selectedTab == .summary else {
      patientSummaryView.isHidden = true
      return
    }
    
    configureBasicUI()
    
    patientSummaryView.isHidden = false
    patientSummaryLabel.text = patient.summary.or("Enter Patient Summary")
    patientSummaryLabel.textColor = patient.summary.isEmptyOrNil ? .defaultText : .secondaryStrong
  }
}
