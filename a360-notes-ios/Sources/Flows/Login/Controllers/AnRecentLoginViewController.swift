//
//  AnRecentLoginViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 06.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

protocol AnRecentLoginOutput {
  var finishFlow: (() -> Void)? { get set }
  var onChangeUser: (() -> Void)? { get set }
  var onAddUser: (() -> Void)? { get set }
  var user: AnUser? { get set }
}

final class AnRecentLoginViewController: AnBaseViewController, AnRecentLoginOutput {
  
  // MARK: - Output
  
  var finishFlow: (() -> Void)?
  var onChangeUser: (() -> Void)?
  var onAddUser: (() -> Void)?
  var user: AnUser?
  
  // MARK: - Outlets
  
  @IBOutlet private weak var changeUserBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var avatarImageView: UIImageView!
  @IBOutlet private weak var nameLabel: UILabel!
  @IBOutlet private weak var emailLabel: UILabel!
  @IBOutlet private weak var passwordTextField: UITextField!
  @IBOutlet private weak var loginButton: UIButton!
  @IBOutlet private weak var bioAuthButton: UIButton!
  @IBOutlet private weak var showHidePasswordButton: UIButton!
  @IBOutlet private weak var versionLabel: UILabel!
  @IBOutlet private var longTapGesture: UILongPressGestureRecognizer!
  
  // MARK: - Private Properties
  
  private lazy var authService: AnAuthService = AnAPIService()
  private lazy var practiceService: AnPracticeService = AnAPIService()
  
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
  
  @IBAction private func onChangeUserAction(_ sender: Any) {
    onChangeUser?()
  }
  
  @IBAction private func onBioAuthAction(_ sender: Any) {
    guard user?.isBiometricAuthEnabled ?? false else {
      let biometryName = AnBioAuthManager.shared.biometryName
      let message = "You can use \(biometryName) only after logging in and enabling \"Use \(biometryName)\" in Settings."
      showAlert(message, source: bioAuthButton)
      return
    }
    Task {
      do {
        try await AnBioAuthManager.shared.authenticateUser()
        handleLogin(forBioAuth: true)
      } catch {
        showErrorBanner(error.localizedDescription)
      }
    }
  }
  
  @IBAction private func onShowHidePasswordAction(_ sender: Any) {
    passwordTextField.isSecureTextEntry.toggle()
    let iconName = passwordTextField.isSecureTextEntry ? "eye.circle" : "eye.slash.circle"
    showHidePasswordButton.setImage(UIImage(systemName: iconName), for: .normal)
  }
  
  @IBAction private func onLoginAction(_ sender: Any) {
    if let password = passwordTextField.text,
       password.isEmpty,
       user?.isBiometricAuthEnabled ?? false {
      onBioAuthAction(sender)
    } else {
      handleLogin()
    }
  }
  
  @IBAction private func onLongTapGesture(_ sender: UILongPressGestureRecognizer) {
    guard sender.state == .began, let sourceView = sender.view else { return }
    showServerEnvironmentSelection(sourceView: sourceView) { [weak self] in
      guard let latestUser = AnUserManager.shared.getLastLoggedInUser() else {
        self?.onAddUser?()
        return
      }
      self?.user = latestUser
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
    
    guard let user else {
      passwordTextField.text = nil
      return
    }
    
    nameLabel.text = user.displayName
    emailLabel.text = user.username
    let diameter = avatarImageView.bounds.width
    avatarImageView.image = UIImage.initialsImage(displayName: user.nameForInitials, diameter: diameter, backgroundColor: user.avatarColor)
    
    bioAuthButton.isHidden = !AnBioAuthManager.shared.isBiometryAvailable
    bioAuthButton.setImage(AnBioAuthManager.shared.icon, for: .normal)
    bioAuthButton.tintColor = user.isBiometricAuthEnabled ? .accent : .secondaryMedium
    loginButton.applyGlass(isProminent: true)
  }
  
  private func handleLogin(forBioAuth: Bool = false) {
    guard let username = user?.username,
          let password = forBioAuth ? user?.password : passwordTextField.text,
          !username.isEmpty,
          !password.isEmpty else {
      showAlert("Please submit Password.", source: passwordTextField, firstResponderAfterProceed: passwordTextField)
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
      guard var user else { return }
      user.info.update(password: password, lastLogin: Date(), profile: profile)
      AnUserManager.shared.saveOrUpdate(user)
      finishFlow?()
    } catch {
      showErrorBanner("Login error", subtitle: error.localizedDescription, duration: GlobalConstants.loginErrorBannerDuration)
    }
  }
}

// MARK: - UITextFieldDelegate

extension AnRecentLoginViewController: UITextFieldDelegate {
  func textFieldShouldReturn(_ textField: UITextField) -> Bool {
    handleLogin()
    return true
  }
}
