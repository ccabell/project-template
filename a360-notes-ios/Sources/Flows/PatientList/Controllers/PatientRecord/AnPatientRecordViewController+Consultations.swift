//
//  AnPatientRecordViewController+Consultations.swift
//  A360Scribe
//
//  Created by Mike Grankin on 13.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SkeletonView
import SwipeCellKit

internal extension AnPatientRecordViewController {
  func updateDataUI(_ state: AnDataState) {
    switch state {
    case .noData, .noSearchResults, .dataAvailable, .loadingMore:
      consultationListTableView.stopSkeletonAnimation()
      consultationListTableView.hideSkeleton()
    case .loading:
      // Fix glitch: prevent offset if pulling to refresh
      if consultationListTableView.contentOffset.y < 0.0 {
        consultationListTableView.setContentOffset(.zero, animated: false)
      }
      consultationListTableView.showAnimatedGradientSkeleton()
    }
    consultationListTableView.reloadData()
    consultationListFilterButton.configuration?.baseBackgroundColor = consultationListFilter.isFilterEmpty ? .surfaceSoft : .buttonDefault
    consultationListFilterButton.configuration?.baseForegroundColor = consultationListFilter.isFilterEmpty ? .textPrimary : .surfaceSoft
    animateFirstCellIfPossible()
  }
  
  func refreshData() {
    consultationListTableView.refreshControl?.endRefreshing()
    searchDebounceTask?.cancel()
    activeSearchTask?.cancel()
    resetPaginationState()
    
    activeSearchTask = Task {
      await fetchConsultations(searchText: consultationListSearchBar.text)
    }
  }
  
  func fetchConsultations(searchText: String? = nil) async {
    guard let patient, !isFetching, currentPagination.hasMorePages else { return }
    isFetching = true
    defer { isFetching = false }
    
    do {
      let response = try await patientService.loadConsultations(patientId: patient.id, searchText: searchText, filter: consultationListFilter, pagination: currentPagination)
      
      if response.page == 1 {
        consultations = response.items
      } else {
        consultations.append(contentsOf: response.items)
      }
      
      currentPagination.update(basedOn: response)
      
      if consultations.isEmpty {
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
      if consultations.isEmpty {
        dataState = .noData
      }
    }
    consultationListTableView.refreshControl?.endRefreshing()
  }
  
  @MainActor
  func resetPaginationState() {
    currentPagination = AnPagination()
    dataState = .loading
    consultations.removeAll()
  }
  
  func configureConsultationsTableView() {
    consultationListTableView.tableFooterView = UIView() // to hide empty cells
    consultationListTableView.register(AnEmptyStateTableViewCell.self)
    consultationListTableView.register(AnLoadingCell.self)
    
    let refreshControl = UIRefreshControl()
    refreshControl.addTarget(self, action: #selector(onPullToRefresh), for: .valueChanged)
    consultationListTableView.refreshControl = refreshControl
  }
  
  @objc
  private func onPullToRefresh() {
    refreshData()
  }
  
  func makeSwipeAction(title: String, imageSystemName: String, needsSeparator: Bool, isActive: Bool = true, handler: @escaping (SwipeAction, IndexPath) -> Void) -> SwipeAction {
    let action: SwipeAction = SwipeAction(style: .default, title: title) { [weak self] action, indexPath in
      handler(action, indexPath)
      guard let cell = self?.consultationListTableView.cellForRow(at: indexPath) as? SwipeTableViewCell else { return }
      cell.hideSwipe(animated: false)
    }
    action.image = UIImage(systemName: imageSystemName)
    action.textColor = isActive ? .primarySoft : .secondarySoft
    action.font = UIFont(name: "PlusJakartaSans-Regular_SemiBold", size: 10.0) ?? UIFont.systemFont(ofSize: 10.0, weight: .semibold)
    action.backgroundColor = .infoBackground
    action.transitionDelegate = AnSwipeCellTransition(needsSeparator: needsSeparator)
    return action
  }
  
  @MainActor
  func animateFirstCellIfPossible() {
    guard dataState.hasData,
          !hasAnimatedFirstCell,
          let cell = consultationListTableView.cellForRow(at: IndexPath(item: 0, section: 0)) as? AnConsultationCell
    else { return }
    hasAnimatedFirstCell = true
    consultationListTableView.layoutIfNeeded()
    
    Task {
      try await Task.sleep(for: .seconds(0.5))
      cell.showSwipe(orientation: .right, animated: true) { [weak cell] _ in
        cell?.hideSwipe(animated: true)
      }
    }
  }
  
  private func finishConsultation(id: String) {
    Task {
      defer {
        hideHUD()
      }
      
      do {
        showHUD(in: consultationListView)
        let consultation = try await consultationService.update(consultationId: id, status: .finished)
        refresh(consultation: consultation)
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
}

// MARK: - UITableViewDelegate methods

extension AnPatientRecordViewController: UITableViewDelegate {
  func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
    tableView.deselectRow(at: indexPath, animated: false)
    guard let patient, dataState.hasData, indexPath.row != consultations.count else { return }
    let consultation = consultations[indexPath.row]
    onShowConsultationProfile?(patient, consultation)
  }
}

// MARK: - UITableViewDataSource methods

extension AnPatientRecordViewController: UITableViewDataSource {
  
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
      return consultations.count + (dataState == .loadingMore ? 1 : 0)
    case .noData, .noSearchResults:
      return 1
    case .loading:
      return 12
    }
  }
  
  func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
    switch dataState {
    case .loading:
      return tableView.dequeue(AnConsultationCell.self, for: indexPath)
    case .dataAvailable, .loadingMore:
      if indexPath.row == consultations.count {
        let cell = tableView.dequeue(AnLoadingCell.self, for: indexPath)
        return cell
      }
      let consultation = consultations[indexPath.row]
      let cell = tableView.dequeue(AnConsultationCell.self, for: indexPath)
      cell.delegate = self
      cell.setup(consultation: consultation)
      return cell
    case .noData, .noSearchResults:
      let cell = tableView.dequeue(AnEmptyStateTableViewCell.self, for: indexPath)
      if consultationListFilter.isFilterEmpty, consultationListSearchBar.text.isEmptyOrNil {
        cell.configure(title: "No Consultations Yet", subtitle: "Tap {subtitleInlineIcon} to start one", icon: "clock.arrow.circlepath", inlineIcon: "waveform.badge.microphone")
      } else {
        cell.configure(title: "No Results", subtitle: "Try refining your search", icon: "magnifyingglass")
      }
      return cell
    }
  }
}

// MARK: - SkeletonTableViewDataSource methods

extension AnPatientRecordViewController: SkeletonTableViewDataSource {
  func collectionSkeletonView(_ skeletonView: UITableView, numberOfRowsInSection section: Int) -> Int {
    return 12
  }
  
  func collectionSkeletonView(_ skeletonView: UITableView, cellIdentifierForRowAt indexPath: IndexPath) -> ReusableCellIdentifier {
    return "AnConsultationCell"
  }
}

// MARK: - UIScrollViewDelegate methods

extension AnPatientRecordViewController {
  func scrollViewDidScroll(_ scrollView: UIScrollView) {
    let offsetY = scrollView.contentOffset.y
    let threshold = scrollView.contentSize.height - scrollView.frame.height * 1.5
    
    guard offsetY > threshold, !isFetching, currentPagination.hasMorePages else { return }
    
    dataState = .loadingMore
    Task {
      await fetchConsultations()
    }
  }
}

// MARK: - UISearchBarDelegate methods

extension AnPatientRecordViewController: UISearchBarDelegate {
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
        await fetchConsultations(searchText: currentSearchText)
      }
    }
  }
  
  func searchBarSearchButtonClicked(_ searchBar: UISearchBar) {
    searchBar.resignFirstResponder()
  }
  
  func searchBarCancelButtonClicked(_ searchBar: UISearchBar) {
    searchBar.resignFirstResponder()
  }
}

// MARK: - SwipeTableViewCellDelegate

extension AnPatientRecordViewController: SwipeTableViewCellDelegate {
  
  func tableView(_ tableView: UITableView, editActionsForRowAt indexPath: IndexPath, for orientation: SwipeActionsOrientation) -> [SwipeAction]? {
    guard orientation == .right,
          dataState.hasData,
          indexPath.row < consultations.count else { return nil }
    let consultation = consultations[indexPath.row]
    let consultationActionAllowed = checkIfConsultationActionAllowed(for: consultation)
    
    let finishAction = makeSwipeAction(title: "Finish", imageSystemName: "flag.pattern.checkered", needsSeparator: false, isActive: consultationActionAllowed) { [weak self] _, _ in
      guard let self, checkIfConsultationActionAllowed(for: consultation, shouldShowAlert: true, indexPath: indexPath) else { return }
      finishConsultation(id: consultation.id)
    }
    let resumeAction = makeSwipeAction(title: "Resume", imageSystemName: "waveform.badge.microphone", needsSeparator: true, isActive: consultationActionAllowed) { [weak self] _, _ in
      guard let self, let patient, checkIfConsultationActionAllowed(for: consultation, shouldShowAlert: true, indexPath: indexPath) else { return }
      onResumeConsultation?(patient, consultation)
    }
    
    return [finishAction, resumeAction].reversed()
  }
  
  func tableView(_ tableView: UITableView, editActionsOptionsForRowAt indexPath: IndexPath, for orientation: SwipeActionsOrientation) -> SwipeOptions {
    var options = SwipeOptions()
    options.expansionStyle = .selection
    options.transitionStyle = .reveal
    return options
  }
  
  private func checkIfConsultationActionAllowed(for consultation: AnConsultation, shouldShowAlert: Bool = false, indexPath: IndexPath? = nil) -> Bool {
    let prohibitedActionMessage = consultation.prohibitedActionMessage?.rawValue
    if shouldShowAlert, let prohibitedActionMessage, let indexPath {
      let cell = consultationListTableView.cellForRow(at: indexPath) as? AnConsultationCell
      showAlert(prohibitedActionMessage, title: "Access restricted", source: cell?.prohibitedActionSource)
    }
    return prohibitedActionMessage == nil
  }
}
