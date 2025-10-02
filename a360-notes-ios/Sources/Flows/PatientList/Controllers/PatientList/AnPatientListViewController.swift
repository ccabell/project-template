//
//  AnPatientListViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation
import UIKit

protocol AnPatientListOutput: AnyObject {
  var onLogout: (() -> Void)? { get set }
  var onSelectPatient: ((AnPatient, AnPatientRecordTab) -> Void)? { get set }
  var onAddPatient: (() -> Void)? { get set }
  var onStartConsultation: ((AnPatient) -> Void)? { get set }
  var onShowFilter: ((AnPatientListFilter) -> Void)? { get set }
  var filter: AnPatientListFilter { get set }
}

final class AnPatientListViewController: AnBaseViewController, AnPatientListOutput {
  
  // MARK: - Output
  
  var onLogout: (() -> Void)?
  var onSelectPatient: ((AnPatient, AnPatientRecordTab) -> Void)?
  var onAddPatient: (() -> Void)?
  var onStartConsultation: ((AnPatient) -> Void)?
  var onShowFilter: ((AnPatientListFilter) -> Void)?
  var filter = AnPatientListFilter() {
    didSet {
      refreshData()
    }
  }

  // MARK: - Outlets
  
  @IBOutlet internal weak var settingsButton: UIBarButtonItem!
  @IBOutlet internal weak var searchBar: UISearchBar!
  @IBOutlet private weak var filterButton: UIButton!
  @IBOutlet internal weak var tableView: UITableView!
  
  // MARK: - Private Properties
  
  private lazy var patientService: AnPatientService = AnAPIService()
  internal var dataState: AnDataState = .noData {
    didSet {
      Task {
        updateDataUI(dataState)
      }
    }
  }
  internal var patients: [AnPatient] = []
  internal var currentPagination = AnPagination()
  internal var isFetching = false
  internal var searchDebounceTask: Task<Void, Never>?
  internal var activeSearchTask: Task<Void, Never>?
  internal var hasAnimatedFirstCell: Bool = false
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureInitialStateUI()
    configureNavigationBarMenu()
    configureTableView()
    configureTimeoutManager()
    refreshData()
  }
  
  deinit {
    AnSessionTimeoutManager.shared.stopMonitoring()
  }
  
  // MARK: - Actions
  
  @IBAction private func onAddPatientAction(_ sender: Any) {
    guard AnUserManager.shared.currentUser?.hasPractice ?? false else {
      showInfoBanner("User can't create patients")
      return
    }
    onAddPatient?()
  }

  @IBAction private func onShowFilterAction(_ sender: Any) {
    onShowFilter?(filter)
  }

  // MARK: - Public Functions
  
  func insert(patient addedPatient: AnPatient) {
    patients.insert(addedPatient, at: 0)
    tableView.reloadData()
    tableView.scrollToRow(at: IndexPath(row: 0, section: 0), at: .top, animated: false)
  }
  
  func refresh(patient updatedPatient: AnPatient) {
    guard let index = patients.firstIndex(where: { $0.id == updatedPatient.id }) else { return }
    patients[index] = updatedPatient
    tableView.reloadRows(at: [IndexPath(row: index, section: 0)], with: .automatic)
  }
  
  // MARK: - Private functions
  
  private func configureTimeoutManager() {
    AnSessionTimeoutManager.shared.startMonitoring()
    NotificationCenter.default.addObserver(self, selector: #selector(performLogout), name: GlobalConstants.Notifications.performLogout.name, object: nil)
  }
  
  internal func handleLogout() {
    Task {
      AnSessionManager.shared.logout()
      onLogout?()
    }
  }
  
  @objc
  private func performLogout(_: NSNotification) {
    handleLogout()
  }
  
  private func configureInitialStateUI() {
    filterButton.applyGlass(isProminent: true)
    dataState = .noData
  }
  
  private func updateDataUI(_ state: AnDataState) {
    switch state {
    case .noData, .noSearchResults, .dataAvailable, .loadingMore:
      tableView.stopSkeletonAnimation()
      tableView.hideSkeleton()
      
    case .loading:
      // Fix glitch: prevent offset if pulling to refresh
      if tableView.contentOffset.y < 0.0 {
        tableView.setContentOffset(.zero, animated: false)
      }
      tableView.showAnimatedGradientSkeleton()
    }
    tableView.reloadData()
    filterButton.configuration?.baseBackgroundColor = filter.isFilterEmpty ? .surfaceSoft : .buttonDefault
    filterButton.configuration?.baseForegroundColor = filter.isFilterEmpty ? .textPrimary : .surfaceSoft
    animateFirstCellIfPossible()
  }
  
  internal func refreshData() {
    tableView.refreshControl?.endRefreshing()
    searchDebounceTask?.cancel()
    activeSearchTask?.cancel()
    resetPaginationState()
    
    activeSearchTask = Task {
      await fetchPatients(searchText: searchBar.text)
    }
  }
  
  internal func fetchPatients(searchText: String? = nil) async {
    guard !isFetching, currentPagination.hasMorePages else { return }
    isFetching = true
    defer { isFetching = false }
    
    do {
      let response = try await patientService.loadPatients(searchText: searchText, filter: filter, pagination: currentPagination)
      
      if response.page == 1 {
        patients = response.items
      } else {
        patients.append(contentsOf: response.items)
      }
      
      currentPagination.update(basedOn: response)
      
      if patients.isEmpty {
        dataState = searchText?.isEmpty == false ? .noSearchResults : .noData
      } else if currentPagination.hasMorePages {
        dataState = .loadingMore
      } else {
        dataState = .dataAvailable
      }
    } catch {
      guard !(error is CancellationError),
            (error as? URLError)?.code != .cancelled
      else { return }
      showErrorBanner(error.localizedDescription)
      if patients.isEmpty {
        dataState = .noData
      }
    }
    tableView.refreshControl?.endRefreshing()
  }
  
  @MainActor
  internal func resetPaginationState() {
    currentPagination = AnPagination()
    dataState = .loading
    patients.removeAll()
  }
}
