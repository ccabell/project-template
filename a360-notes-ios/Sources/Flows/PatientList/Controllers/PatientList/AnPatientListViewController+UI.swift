//
//  AnPatientListViewController+UI.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SkeletonView
import SwipeCellKit

internal extension AnPatientListViewController {
  
  func configureNavigationBarMenu() {
    var mainItems: [UIMenuElement] = []
    var bottomItems: [UIMenuElement] = []
    
    if let user = AnUserManager.shared.currentUser {
      let diameter = 64.0
      let lastName = user.profile?.expert?.lastName ?? user.displayName
      let firstName = user.profile?.expert?.firstName
      let avatar = UIImage.initialsImage(displayName: user.nameForInitials, diameter: diameter, backgroundColor: user.avatarColor)
      let profileAction = UIAction(title: lastName, subtitle: firstName, image: avatar, attributes: .disabled) { _ in }
      mainItems.append(profileAction)
    }
    
    if AnBioAuthManager.shared.isBiometryAvailable {
      let title = AnBioAuthManager.shared.actionTitle
      let icon = AnBioAuthManager.shared.icon
      let isEnabled = AnUserManager.shared.currentUser?.isBiometricAuthEnabled ?? false
      let state: UIMenuElement.State = isEnabled ? .on : .off
      let biometryAction = UIAction(title: title, image: icon, state: state) { [weak self] _ in
        self?.handleBiometryAction()
      }
      mainItems.append(biometryAction)
    }
    
    let mainGroup: UIMenu = UIMenu(title: "", options: .displayInline, children: mainItems)
    
    guard let logoutIcon = UIImage(named: "logout-icon") else { return }
    let logoutAction = UIAction(title: "Log Out", image: logoutIcon) { [weak self] _ in
      self?.handleLogout()
    }
    bottomItems.append(logoutAction)
    
    guard let infoIcon = UIImage(systemName: "info.circle") else { return }
    let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
    let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? ""
    let message = "v\(version) (\(build))"
    let aboutAction = UIAction(title: "Aesthetics360", subtitle: message, image: infoIcon, attributes: .disabled) { _ in }
    bottomItems.append(aboutAction)
    
    let bottomGroup: UIMenu = UIMenu(title: "", options: .displayInline, children: bottomItems)
    
    settingsButton.menu = UIMenu(title: "", children: [mainGroup, bottomGroup])
  }
  
  private func handleBiometryAction() {
    guard let user = AnUserManager.shared.currentUser else { return }
    
    if user.isBiometricAuthEnabled {
      toggleBiometricAuth(for: user)
      return
    }
    
    Task {
      do {
        try await AnBioAuthManager.shared.authenticateUser()
        toggleBiometricAuth(for: user)
      } catch {
        showErrorBanner("Authentication Error", subtitle: error.localizedDescription)
      }
    }
  }
  
  private func toggleBiometricAuth(for user: AnUser) {
    var user = user
    user.info.toggleBiometricAuthEnabled()
    AnUserManager.shared.saveOrUpdate(user)
    configureNavigationBarMenu()
  }
  
  func configureTableView() {
    tableView.tableFooterView = UIView() // to hide empty cells
    tableView.register(AnEmptyStateTableViewCell.self)
    tableView.register(AnLoadingCell.self)
    
    let refreshControl = UIRefreshControl()
    refreshControl.addTarget(self, action: #selector(onPullToRefresh), for: .valueChanged)
    tableView.refreshControl = refreshControl
  }
  
  @objc
  private func onPullToRefresh() {
    refreshData()
  }
  
  @MainActor
  func animateFirstCellIfPossible() {
    guard dataState.hasData,
          !hasAnimatedFirstCell,
          let cell = tableView.cellForRow(at: IndexPath(item: 0, section: 0)) as? AnPatientCell
    else { return }
    hasAnimatedFirstCell = true
    tableView.layoutIfNeeded()
    
    Task {
      try await Task.sleep(for: .seconds(0.5))
      cell.showSwipe(orientation: .right, animated: true) { [weak cell] _ in
        cell?.hideSwipe(animated: true)
      }
    }
  }
  
  func makeSwipeAction(title: String, imageSystemName: String, needsSeparator: Bool, isActive: Bool = true, handler: @escaping (SwipeAction, IndexPath) -> Void) -> SwipeAction {
    let action: SwipeAction = SwipeAction(style: .default, title: title) { [weak self] action, indexPath in
      handler(action, indexPath)
      guard let cell = self?.tableView.cellForRow(at: indexPath) as? SwipeTableViewCell else { return }
      cell.hideSwipe(animated: false)
    }
    action.image = UIImage(systemName: imageSystemName)
    action.textColor = isActive ? .primarySoft : .secondarySoft
    action.font = UIFont(name: "PlusJakartaSans-Regular_SemiBold", size: 10.0) ?? UIFont.systemFont(ofSize: 10.0, weight: .semibold)
    action.backgroundColor = .infoBackground
    action.transitionDelegate = AnSwipeCellTransition(needsSeparator: needsSeparator)
    return action
  }
}

// MARK: - UITableViewDelegate methods

extension AnPatientListViewController: UITableViewDelegate {
  func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
    tableView.deselectRow(at: indexPath, animated: false)
    guard dataState.hasData, indexPath.row != patients.count else { return }
    let patient = patients[indexPath.row]
    onSelectPatient?(patient, .history)
  }
}

// MARK: - UITableViewDataSource methods

extension AnPatientListViewController: UITableViewDataSource {
  
  func tableView(_ tableView: UITableView, heightForRowAt indexPath: IndexPath) -> CGFloat {
    switch dataState {
    case .noData, .noSearchResults:
      return tableView.height - tableView.adjustedContentInset.top - tableView.adjustedContentInset.bottom
    default:
      return UITableView.automaticDimension
    }
  }
  
  func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
    switch dataState {
    case .dataAvailable, .loadingMore:
      return patients.count + (dataState == .loadingMore ? 1 : 0)
    case .noData, .noSearchResults:
      return 1
    case .loading:
      return 12
    }
  }
  
  func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
    switch dataState {
    case .loading:
      return tableView.dequeue(AnPatientCell.self, for: indexPath)
    case .dataAvailable, .loadingMore:
      if indexPath.row == patients.count {
        let cell = tableView.dequeue(AnLoadingCell.self, for: indexPath)
        return cell
      }
      let patient = patients[indexPath.row]
      let cell = tableView.dequeue(AnPatientCell.self, for: indexPath)
      cell.delegate = self
      cell.setup(patient: patient)
      cell.onProfileTabAction = { [weak self] patient, tab in
        self?.onSelectPatient?(patient, tab)
      }
      cell.onStartConsultationAction = { [weak self] patient in
        guard patient.isActive ?? false else {
          self?.showInactivePatientAlert()
          return
        }
        self?.onStartConsultation?(patient)
      }
      return cell
    case .noData, .noSearchResults:
      let cell = tableView.dequeue(AnEmptyStateTableViewCell.self, for: indexPath)
      cell.configure(title: "No Patients Yet", subtitle: "Tap {subtitleInlineIcon} to add one", icon: "person.2", inlineIcon: "plus")
      return cell
    }
  }
}

// MARK: - SkeletonTableViewDataSource methods

extension AnPatientListViewController: SkeletonTableViewDataSource {
  func collectionSkeletonView(_ skeletonView: UITableView, numberOfRowsInSection section: Int) -> Int {
    return 12
  }
  
  func collectionSkeletonView(_ skeletonView: UITableView, cellIdentifierForRowAt indexPath: IndexPath) -> ReusableCellIdentifier {
    return "AnPatientCell"
  }
}

// MARK: - UIScrollViewDelegate methods

extension AnPatientListViewController {
  func scrollViewDidScroll(_ scrollView: UIScrollView) {
    let offsetY = scrollView.contentOffset.y
    let threshold = scrollView.contentSize.height - scrollView.frame.height * 1.5
    
    guard offsetY > threshold, !isFetching, currentPagination.hasMorePages else { return }
    
    dataState = .loadingMore
    Task {
      await fetchPatients()
    }
  }
}

// MARK: - UISearchBarDelegate methods

extension AnPatientListViewController: UISearchBarDelegate {
  func searchBar(_ searchBar: UISearchBar, textDidChange searchText: String) {
    let currentSearchText = searchText
    searchDebounceTask?.cancel()
    activeSearchTask?.cancel()
    
    guard !currentSearchText.isEmpty else {
      refreshData()
      return
    }
    
    searchDebounceTask = Task {
      try? await Task.sleep(for: .seconds(0.5))
      
      await MainActor.run {
        resetPaginationState()
      }
      
      activeSearchTask = Task {
        await fetchPatients(searchText: currentSearchText)
      }
    }
  }
  
  func searchBarSearchButtonClicked(_ searchBar: UISearchBar) {
    view.endEditing(true)
  }
}

// MARK: - SwipeTableViewCellDelegate

extension AnPatientListViewController: SwipeTableViewCellDelegate {
  
  func tableView(_ tableView: UITableView, editActionsForRowAt indexPath: IndexPath, for orientation: SwipeActionsOrientation) -> [SwipeAction]? {
    guard orientation == .right,
          dataState.hasData,
          indexPath.row < patients.count else { return nil }
    let patient = patients[indexPath.row]
    let patientIsActive = patient.isActive ?? false
    
    var swipeActions: [SwipeAction] = []
    
    let historyAction = makeSwipeAction(title: "History", imageSystemName: "clock.arrow.circlepath", needsSeparator: false) { [weak self] _, _ in
      self?.onSelectPatient?(patient, .history)
    }
    let summaryAction = makeSwipeAction(title: "Summary", imageSystemName: "doc.plaintext", needsSeparator: true) { [weak self] _, _ in
      self?.onSelectPatient?(patient, .summary)
    }
    let profileAction = makeSwipeAction(title: "Profile", imageSystemName: "person.text.rectangle", needsSeparator: true) { [weak self] _, _ in
      self?.onSelectPatient?(patient, .profile)
    }
    swipeActions = [historyAction, summaryAction, profileAction]
    if !UIDevice.current.isPad {
      let startAction = makeSwipeAction(title: "Start", imageSystemName: "waveform.badge.microphone", needsSeparator: true, isActive: patientIsActive) { [weak self] _, _ in
        guard patientIsActive else {
          self?.showInactivePatientAlert()
          return
        }
        self?.onStartConsultation?(patient)
      }
      swipeActions.append(startAction)
    }
    
    return swipeActions.reversed()
  }
  
  func tableView(_ tableView: UITableView, editActionsOptionsForRowAt indexPath: IndexPath, for orientation: SwipeActionsOrientation) -> SwipeOptions {
    var options = SwipeOptions()
    options.expansionStyle = .selection
    options.transitionStyle = .reveal
    return options
  }
}
