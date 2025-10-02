//
//  AnNotificationManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 03.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UserNotifications

final class AnNotificationManager {
  
  // MARK: - Public Properties
  
  static let shared = AnNotificationManager()
  
  // MARK: - Private Properties
  
  let recordingNotificationIdentifier = "AnRecordingReminder"
  
  // MARK: - Public Functions
  
  func requestAuthorizationIfNeeded() {
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
      if let error {
        print("Notification authorization error: \(error.localizedDescription)")
      } else {
        print("Notification authorization granted: \(granted)")
      }
    }
  }
  
  func scheduleRecordingReminder() {
    clearRecordingReminder()
    
    let content = UNMutableNotificationContent()
    content.title = "Recording Still Active"
    content.body  = "Consultation audio is still being captured in the background."
    content.sound = .default
    let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1.5, repeats: false)
    let request = UNNotificationRequest(identifier: recordingNotificationIdentifier, content: content, trigger: trigger)
    UNUserNotificationCenter.current().add(request) { error in
      guard let error else { return }
      print("Notification error: \(error.localizedDescription)")
    }
  }
  
  func clearRecordingReminder() {
    UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [recordingNotificationIdentifier])
    UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: [recordingNotificationIdentifier])
  }
}
