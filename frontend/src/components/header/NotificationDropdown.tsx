import { apiClient } from "@/api/client";
import { formatUtcTimestamp } from "@/utils/date";
import { useEffect, useState } from "react";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";

type ScanNotification = {
  scan_id: string;
  account_id: number;
  account_name: string;
  status: string;
  triggered_by_username: string;
  triggered_by_email: string;
  triggered_at: string;
};

function formatTriggeredAt(value: string) {
  return formatUtcTimestamp(value);
}

export default function NotificationDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<ScanNotification[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasUnread, setHasUnread] = useState(true);

  const closeDropdown = () => setIsOpen(false);

  const handleClick = () => {
    setIsOpen((open) => !open);
    setHasUnread(false);
  };

  useEffect(() => {
    if (!isOpen) return;

    setIsLoading(true);
    apiClient
      .get<ScanNotification[]>("/api/v1/notifications")
      .then(({ data }) => setNotifications(data))
      .catch(() => setNotifications([]))
      .finally(() => setIsLoading(false));
  }, [isOpen]);

  return (
    <div className="relative">
      <button
        className="dropdown-toggle relative flex h-11 w-11 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
        onClick={handleClick}
        aria-label="Notifications"
      >
        {hasUnread && notifications.length > 0 && (
          <span className="absolute inset-e-0 top-0.5 z-10 h-2 w-2 rounded-full bg-orange-400" />
        )}
        <svg className="fill-current" width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
          <path fillRule="evenodd" clipRule="evenodd" d="M10.75 2.29248C10.75 1.87827 10.4143 1.54248 10 1.54248C9.58583 1.54248 9.25004 1.87827 9.25004 2.29248V2.83613C6.08266 3.20733 3.62504 5.9004 3.62504 9.16748V14.4591H3.33337C2.91916 14.4591 2.58337 14.7949 2.58337 15.2091C2.58337 15.6234 2.91916 15.9591 3.33337 15.9591H4.37504H15.625H16.6667C17.0809 15.9591 17.4167 15.6234 16.6667 14.4591H16.375V9.16748C16.375 5.9004 13.9174 3.20733 10.75 2.83613V2.29248ZM14.875 14.4591V9.16748C14.875 6.47509 12.6924 4.29248 10 4.29248C7.30765 4.29248 5.12504 6.47509 5.12504 9.16748V14.4591H14.875ZM8.00004 17.7085C8.00004 18.1228 8.33583 18.4585 8.75004 18.4585H11.25C11.6643 18.4585 12 18.1228 12 17.7085C12 17.2943 11.6643 16.9585 11.25 16.9585H8.75004C8.33583 16.9585 8.00004 17.2943 8.00004 17.7085Z" fill="currentColor" />
            <path fillRule="evenodd" clipRule="evenodd" d="M10.75 2.29248C10.75 1.87827 10.4143 1.54248 10 1.54248C9.58583 1.54248 9.25004 1.87827 9.25004 2.29248V2.83613C6.08266 3.20733 3.62504 5.9004 3.62504 9.16748V14.4591H3.33337C2.91916 14.4591 2.58337 14.7949 2.58337 15.2091C2.58337 15.6234 2.91916 15.9591 3.33337 15.9591H4.37504H15.625H16.6667C17.0809 15.9591 17.4167 15.6234 17.4167 15.2091C17.4167 14.7949 17.0809 14.4591 16.6667 14.4591H16.375V9.16748C16.375 5.9004 13.9174 3.20733 10.75 2.83613V2.29248ZM14.875 14.4591V9.16748C14.875 6.47509 12.6924 4.29248 10 4.29248C7.30765 4.29248 5.12504 6.47509 5.12504 9.16748V14.4591H14.875ZM8.00004 17.7085C8.00004 18.1228 8.33583 18.4585 8.75004 18.4585H11.25C11.6643 18.4585 12 18.1228 12 17.7085C12 17.2943 11.6643 16.9585 11.25 16.9585H8.75004C8.33583 16.9585 8.00004 17.2943 8.00004 17.7085Z" fill="currentColor" />
        </svg>
      </button>

      <Dropdown
        isOpen={isOpen}
        onClose={closeDropdown}
        className="absolute -inset-s-13.5 mt-4.25 flex h-120 w-87.5 flex-col rounded-2xl border border-gray-200 bg-white p-3 shadow-theme-lg sm:w-90.25 xl:inset-s-auto xl:inset-e-0 dark:border-gray-800 dark:bg-gray-dark"
      >
        <div className="mb-3 flex items-center justify-between border-b border-gray-100 pb-3 dark:border-gray-700">
          <h5 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Notifications</h5>
          <button onClick={closeDropdown} className="text-gray-500 transition hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200" aria-label="Close notifications">
            <span aria-hidden="true">x</span>
          </button>
        </div>

        <ul className="custom-scrollbar flex h-auto flex-col overflow-y-auto">
          {isLoading && <li className="p-4 text-sm text-gray-500">Loading scan activity...</li>}
          {!isLoading && notifications.length === 0 && (
            <li className="p-4 text-sm text-gray-500">No user-triggered scans yet.</li>
          )}
          {notifications.map((notification) => (
            <li key={notification.scan_id}>
              <DropdownItem
                onItemClick={closeDropdown}
                to={`/accounts/${notification.account_id}`}
                className="flex gap-3 border-b border-gray-100 p-3 px-4.5 py-3 hover:bg-gray-100 dark:border-gray-800 dark:hover:bg-white/5"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
                  {notification.triggered_by_username.slice(0, 2).toUpperCase()}
                </span>
                <span className="block min-w-0">
                  <span className="mb-1.5 block text-theme-sm text-gray-500 dark:text-gray-400">
                    <span className="font-medium text-gray-800 dark:text-white/90">
                      {notification.triggered_by_username}
                    </span>{" "}
                    triggered a scan for{" "}
                    <span className="font-medium text-gray-800 dark:text-white/90">
                      {notification.account_name}
                    </span>
                  </span>
                  <span className="flex items-center gap-2 text-theme-xs text-gray-500 dark:text-gray-400">
                    <span>{notification.status}</span>
                    <span className="h-1 w-1 rounded-full bg-gray-400" />
                    <span>{formatTriggeredAt(notification.triggered_at)}</span>
                  </span>
                </span>
              </DropdownItem>
            </li>
          ))}
        </ul>
      </Dropdown>
    </div>
  );
}
