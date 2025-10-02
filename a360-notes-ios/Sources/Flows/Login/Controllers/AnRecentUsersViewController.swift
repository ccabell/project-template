//
//  AnRecentUsersViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 06.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnRecentUsersOutput {
  var onSelectUser: ((AnUser) -> Void)? { get set }
  var onAddUser: (() -> Void)? { get set }
}

final class AnRecentUsersViewController: AnBaseViewController, AnRecentUsersOutput {
  
  // MARK: - Output
  
  var onSelectUser: ((AnUser) -> Void)?
  var onAddUser: (() -> Void)?
  
  // MARK: - Outlets
  
  @IBOutlet private weak var tableView: UITableView!
  @IBOutlet private weak var tableViewHeightConstraint: NSLayoutConstraint!
  @IBOutlet private weak var versionLabel: UILabel!
  @IBOutlet private var longTapGesture: UILongPressGestureRecognizer!

  // MARK: - Private Properties
  
  private var users: [AnUser] = []
  private let minVisibleRows: CGFloat = 1.0
  private let maxVisibleRows: CGFloat = 5.25
  private var didLayoutTable = false
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureUI()
    loadUsers()
  }
  
  override func viewDidLayoutSubviews() {
    super.viewDidLayoutSubviews()
    guard !didLayoutTable else { return }
    didLayoutTable = true
    updateTableHeight()
  }
  
  // MARK: - Actions
  
  @IBAction private func onHelpAction(_ sender: Any) {
    showInternalBrowser(with: GlobalLinks.ExternalLinks.loginSupport.url)
  }

  @IBAction private func onAddUserAction(_ sender: Any) {
    onAddUser?()
  }
  
  @IBAction private func onLongTapGesture(_ sender: UILongPressGestureRecognizer) {
    guard sender.state == .began, let sourceView = sender.view else { return }
    showServerEnvironmentSelection(sourceView: sourceView) { [weak self] in
      self?.loadUsers()
    }
  }
  
  // MARK: - Private Functions
  
  private func loadUsers() {
    users = AnUserManager.shared.recentUsers() ?? []
    guard !users.isEmpty else {
      onAddUser?()
      return
    }
    tableView.reloadData()
    Task {
      @MainActor in
      await Task.yield()
      updateTableHeight()
    }
  }
  
  private func configureUI() {
    convertNavigationTitleToImage()
    navigationItem.titleView?.isUserInteractionEnabled = true
    navigationItem.titleView?.addGestureRecognizer(longTapGesture)

    let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
    let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? ""
    versionLabel.text = "v\(version) (\(build))"

    configureTableView()
  }
  
  private func configureTableView() {
    tableView.rowHeight = UITableView.automaticDimension
    tableView.tableFooterView = UIView() // to hide empty cells
  }
  
  private func deleteUser(_ user: AnUser, source: UIPopoverPresentationControllerSourceItem?) {
    showAlert("Are you sure you want to remove \(user.username)?",
              title: "Remove User",
              proceedTitle: "Remove",
              proceedStyle: .destructive,
              cancelTitle: "Cancel",
              source: source) { [weak self] in
      AnUserManager.shared.deleteUser(username: user.username)
      self?.loadUsers()
    }
  }
  
  private func updateTableHeight() {
    tableView.layoutIfNeeded()
    let contentHeight = tableView.contentSize.height
    let rowCount = CGFloat(tableView.numberOfRows(inSection: 0))
    let rowHeight = rowCount > 0.0 ? contentHeight / rowCount : 0.0
    let minHeight = rowHeight * minVisibleRows
    let maxHeight = rowHeight * maxVisibleRows
    let newHeight = min(max(contentHeight, minHeight), maxHeight)
    tableViewHeightConstraint.constant = newHeight
    tableView.isScrollEnabled = contentHeight > maxHeight
  }
}

// MARK: - UITableViewDelegate

extension AnRecentUsersViewController: UITableViewDelegate {
  func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
    tableView.deselectRow(at: indexPath, animated: false)
    onSelectUser?(users[indexPath.row])
  }
}

// MARK: - UITableViewDataSource

extension AnRecentUsersViewController: UITableViewDataSource {
  
  func tableView(_ tableView: UITableView, heightForRowAt indexPath: IndexPath) -> CGFloat {
    return UITableView.automaticDimension
  }
  
  func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
    return users.count
  }
  
  func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
    guard !users.isEmpty else { return UITableViewCell() }
    let recentUserCell = tableView.dequeue(AnRecentUserCell.self, for: indexPath)
    let user = users[indexPath.row]
    recentUserCell.setup(user: user)
    recentUserCell.onDelete = { [weak self] user, source in
      self?.deleteUser(user, source: source)
    }
    return recentUserCell
  }
}
