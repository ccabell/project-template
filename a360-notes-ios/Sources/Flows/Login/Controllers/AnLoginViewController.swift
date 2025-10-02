//
//  AnLoginViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 29.01.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnLoginOutput {
  var finishFlow: (() -> Void)? { get set }
  var onSelectUser: (() -> Void)? { get set }
}

final class AnLoginViewController: AnBaseViewController, AnLoginOutput {
  
  // MARK: - Output
  
  var finishFlow: (() -> Void)?
  var onSelectUser: (() -> Void)?
  
  // MARK: - Outlets
  
  @IBOutlet private weak var changeUserBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var usernameTextField: UITextField!
  @IBOutlet private weak var passwordTextField: UITextField!
  @IBOutlet private weak var showHidePasswordButton: UIButton!
  @IBOutlet private weak var loginButton: UIButton!
  @IBOutlet private weak var versionLabel: UILabel!
  @IBOutlet private var longTapGesture: UILongPressGestureRecognizer!
  
  // MARK: - Private Properties
  
  private lazy var authService = AnAPIService()
  private lazy var practiceService = AnAPIService()
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureUI()
    keyboardReturnManager.lastTextInputViewReturnKeyType = .continue
  }
  
  // MARK: - Actions
  
  @IBAction private func onHelpAction(_ sender: Any) {
    showInternalBrowser(with: GlobalLinks.ExternalLinks.loginSupport.url)
  }
  
  @IBAction private func onSelectUserAction(_ sender: Any) {
    onSelectUser?()
  }
  
  @IBAction private func onShowHidePasswordAction(_ sender: Any) {
    passwordTextField.isSecureTextEntry.toggle()
    let iconName = passwordTextField.isSecureTextEntry ? "eye.circle" : "eye.slash.circle"
    showHidePasswordButton.setImage(UIImage(systemName: iconName), for: .normal)
  }
  
  @IBAction private func onLoginAction(_ sender: Any) {
    handleLogin()
  }
  
  @IBAction private func onLongTapGesture(_ sender: UILongPressGestureRecognizer) {
    guard sender.state == .began, let sourceView = sender.view else { return }
    showServerEnvironmentSelection(sourceView: sourceView) { [weak self] in
      self?.configureUI()
    }
  }
  
  // MARK: - Private Functions
  
  private func configureUI() {
    convertNavigationTitleToImage()
    navigationItem.titleView?.isUserInteractionEnabled = true
    navigationItem.titleView?.addGestureRecognizer(longTapGesture)
    
    let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
    let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? ""
    versionLabel.text = "v\(version) (\(build))"
    
    let hasRecentUsers = !(AnUserManager.shared.recentUsers()?.isEmpty ?? true)
    changeUserBarButtonItem.isHidden = !hasRecentUsers
    loginButton.applyGlass(isProminent: true)
  }
  
  private func handleLogin() {
    guard let username = usernameTextField.text,
          let password = passwordTextField.text,
          !username.isEmpty,
          !password.isEmpty
    else {
      let source = usernameTextField.text?.isEmpty ?? true ? usernameTextField : passwordTextField
      showAlert("Please submit Email and Password.", source: source, firstResponderAfterProceed: source)
      return
    }
    
    Task {
      loginButton.configuration?.showsActivityIndicator = true
      loginButton.isUserInteractionEnabled = false
      
      defer {
        loginButton.configuration?.showsActivityIndicator = false
        loginButton.isUserInteractionEnabled = true
      }
      
      await signIn(username: username, password: password)
    }
  }
  
  private func signIn(username: String, password: String) async {
    do {
      try await authService.login(username: username, password: password)
      let profile = try await practiceService.userProfile()
      let user = AnUser(username: username, password: password, profile: profile)
      AnUserManager.shared.saveOrUpdate(user)
      finishFlow?()
    } catch {
      showErrorBanner("Login error", subtitle: error.localizedDescription, duration: GlobalConstants.loginErrorBannerDuration)
    }
  }
}

// MARK: - UITextFieldDelegate

extension AnLoginViewController: UITextFieldDelegate {
  func textFieldShouldReturn(_ textField: UITextField) -> Bool {
    if textField == passwordTextField {
      handleLogin()
    }
    return true
  }
}
