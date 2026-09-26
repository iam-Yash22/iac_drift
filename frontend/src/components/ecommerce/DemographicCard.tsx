"use client";

import { MoreDotIcon } from "@/icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Dropdown } from "../ui/dropdown/Dropdown";
import { DropdownItem } from "../ui/dropdown/DropdownItem";
type ScanStatus = {
  account_id: number;
  status: string | null;
};

export default function DemographicCard({
  latestScans,
}: {
  latestScans: ScanStatus[];
}) {
  const { t } = useTranslation("ecommerce.demographic");
  const { t: tCommon } = useTranslation("common");
  const [isOpen, setIsOpen] = useState(false);

  function toggleDropdown() {
    setIsOpen(!isOpen);
  }

  function closeDropdown() {
    setIsOpen(false);
  }
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 dark:border-gray-800 dark:bg-white/3">
      <div className="flex justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {t("title")}
          </h3>
          <p className="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
            {t("subtitle")}
          </p>
        </div>

        <div className="relative h-fit">
          <button onClick={toggleDropdown} className="dropdown-toggle">
            <MoreDotIcon className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-300" />
          </button>
          <Dropdown
            isOpen={isOpen}
            onClose={closeDropdown}
            className="w-40 p-2"
          >
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-left font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {tCommon("viewMore")}
            </DropdownItem>
            <DropdownItem
              onItemClick={closeDropdown}
              className="flex w-full rounded-lg text-left font-normal text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-white/5 dark:hover:text-gray-300"
            >
              {tCommon("delete")}
            </DropdownItem>
          </Dropdown>
        </div>
      </div>
      <div className="space-y-5">
        {latestScans.map((scan) => (
          <div key={scan.account_id} className="flex items-center justify-between">
            <div>
              <p className="text-theme-sm font-semibold text-gray-800 dark:text-white/90">
                Account {scan.account_id}
              </p>
              <span className="block text-theme-xs text-gray-500 dark:text-gray-400">
                Latest scan status
              </span>
            </div>
            <p className="text-theme-sm font-medium text-gray-800 dark:text-white/90">
              {scan.status ?? "Not scanned"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
