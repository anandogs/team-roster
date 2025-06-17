document.addEventListener("alpine:init", () => {
  // Filters Store
  Alpine.store("filters", {
    // State
    month: "Quarter",
    selectedBusinessUnits: [],
    selectedCustomers: [],
    selectedLocations: [],
    availableLocations: ["Onsite", "Offshore"],
    selectedBillableStatus: [],
    availableBillableStatus: [
      { value: "Y", label: "Billable" },
      { value: "N", label: "Non-Billable" },
    ],
    businessUnits: [],
    customers: [],
    periodData: {},

    // Helper method to check if audit log has entries
    hasAuditLogEntries() {
      const stored = localStorage.getItem("roster-audit-log");
      const auditLog = stored ? JSON.parse(stored) : [];
      return auditLog.length > 0;
    },

    // Helper method to clear audit log and refresh
    clearAuditLogAndRefresh() {
      Alpine.store("employees").clearAuditLog();

      // Show brief success message
      window.dispatchEvent(
        new CustomEvent("show-toast", {
          detail: {
            title: "Clearing Changes",
            description: "Refreshing page in 2 seconds...",
            type: "success",
          },
        })
      );

      // Auto-refresh after 2 seconds
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    },
    // Add this getter to the filters store
    get canMakeChanges() {
      return this.selectedCustomers.length === 1;
    },

    get customerSelectionMessage() {
      if (this.selectedCustomers.length === 0) {
        return "No customer selected. Please select one customer to continue.";
      } else if (this.selectedCustomers.length > 1) {
        return `${this.selectedCustomers.length} customers selected. Please select only one customer to make changes.`;
      }
      return "";
    },

    // Enhanced filter update method with confirmation
    async updateFiltersWithConfirmation(filterType = "general") {
      // Check if there are audit log entries
      if (this.hasAuditLogEntries()) {
        const filterTypeText =
          filterType === "month"
            ? "time period"
            : filterType === "businessUnit"
            ? "business unit"
            : filterType === "customer"
            ? "customer selection"
            : "filters";

        const confirmed = confirm(
          `Changing the ${filterTypeText} will reset all roster changes you've made. ` +
            `This will clear your audit log and refresh the page.\n\n` +
            `Do you want to continue?`
        );

        if (!confirmed) {
          // Revert the filter change by restoring previous state
          this.revertFilterChange(filterType);
          return false;
        } else {
          // User confirmed, clear audit log and refresh
          this.clearAuditLogAndRefresh();
          return true;
        }
      }

      // No audit log entries, proceed with normal filter update
      this.updateFilters();
      return true;
    },

    // Method to revert filter changes when user cancels
    revertFilterChange(filterType) {
      // This method will restore the UI elements to their previous state
      setTimeout(() => {
        switch (filterType) {
          case "month":
            // Revert month display
            this.updateMonthDisplay();
            break;
          case "businessUnit":
            // Revert business unit checkboxes
            this.updateBusinessUnitOptions();
            break;
          case "customer":
            // Revert customer checkboxes
            this.updateCustomerOptions();
            break;
        }
      }, 50);
    },

    // Method to update month display based on current state
    updateMonthDisplay() {
      const displayElement = document.getElementById("month-display");
      if (displayElement) {
        const displayText =
          this.month === "Quarter"
            ? "Quarter"
            : this.periodData[this.month] || this.month;
        displayElement.textContent = displayText;
      }
    },

    // Initialization
    async init() {
      const [periodResponse, customersResponse] = await Promise.all([
        fetch("/api/period"),
        fetch("/api/customers"),
      ]);

      const periodData = await periodResponse.json();
      const customersData = await customersResponse.json();

      this.businessUnits = [...new Set(customersData.map((c) => c.FinalBU))];
      this.periodData = periodData;
      const uniqueCustomers = [];
      const seenCustomers = new Set();
      customersData.forEach((c) => {
        if (!seenCustomers.has(c.PrismCustomerGroup)) {
          seenCustomers.add(c.PrismCustomerGroup);
          uniqueCustomers.push({
            PrismCustomerGroup: c.PrismCustomerGroup,
            FinalBU: c.FinalBU,
          });
        }
      });
      this.customers = uniqueCustomers;

      this.selectedCustomers =
        this.customers.length > 0 ? [this.customers[0].PrismCustomerGroup] : [];
      this.selectedLocations = [...this.availableLocations];
      this.selectedBillableStatus = [
        ...this.availableBillableStatus.map((s) => s.value),
      ];
      this.selectedBusinessUnits =
        this.businessUnits.length > 0 ? [this.businessUnits[0]] : [];

      if (periodData.QTR) {
        document.querySelector(".bg-neutral-800 .text-white").textContent =
          periodData.QTR;
      }

      this.populateOptions();

      setTimeout(() => {
        this.populateOptions();
      }, 1000);
      this.retryLocationAndBillablePopulation();
    },

    retryLocationAndBillablePopulation() {
      let attempts = 0;
      const maxAttempts = 50; // 50 attempts over 10 seconds

      const tryPopulate = () => {
        attempts++;

        const locationOptions = document.getElementById("location-options");
        const billableOptions = document.getElementById("billable-options");

        if (locationOptions) {
          this.updateLocationOptions();
        }
        if (billableOptions) {
          this.updateBillableOptions();
        }

        // If both found or max attempts reached, stop trying
        if ((locationOptions && billableOptions) || attempts >= maxAttempts) {
          console.log(`Filter population completed after ${attempts} attempts`);
          return;
        }

        // Try again in 200ms
        setTimeout(tryPopulate, 200);
      };

      setTimeout(tryPopulate, 1000); // Start after 1 second
    },

    // UI Population Methods
    populateOptions() {
      this.populateMonthOptions();
      this.updateCustomerOptions();
      this.updateLocationOptions();
      this.updateBillableOptions();
      this.updateBusinessUnitOptions();
    },

    populateBusinessUnitOptions() {
      const buOptions = document.getElementById("bu-options");
      if (buOptions) {
        buOptions.innerHTML = this.businessUnits
          .map(
            (bu) => `
                <button
                    class="w-full flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm"
                    @click="open = false"
                    onclick="selectBusinessUnit('${bu}')"
                >
                    <svg class="mr-2 h-4 w-4 opacity-0" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M20 6L9 17l-5-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ${bu}
                </button>
            `
          )
          .join("");
      }
    },

    populateMonthOptions() {
      ["M1", "M2", "M3"].forEach((monthKey) => {
        const button = document.querySelector(
          `button[onclick="selectMonth('${monthKey}')"]`
        );
        if (button && this.periodData[monthKey]) {
          button.onclick = () =>
            this.selectMonth(monthKey, this.periodData[monthKey]);
          button.innerHTML = `
                    <svg class="mr-2 h-4 w-4 opacity-0" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M20 6L9 17l-5-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    ${this.periodData[monthKey]}
                `;
        }
      });
    },

    updateBusinessUnitOptions() {
      const buOptions = document.getElementById("bu-options");
      if (buOptions) {
        buOptions.innerHTML = this.businessUnits
          .map(
            (bu) => `
            <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
                <input
                    type="radio"
                    name="business-unit-selection"
                    value="${bu}"
                    class="mr-3 h-4 w-4 border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500"
                    onchange="selectBusinessUnitWithConfirmation('${bu}')"
                    ${this.selectedBusinessUnits.includes(bu) ? "checked" : ""}
                >
                <span class="truncate">${bu}</span>
            </label>
        `
          )
          .join("");

        this.updateBusinessUnitDisplay();
      }
    },

    async selectBusinessUnitWithConfirmation(bu) {
      const previousState = [...this.selectedBusinessUnits];
      this.selectedBusinessUnits = [bu]; // Only select one BU

      const confirmed = await this.updateFiltersWithConfirmation(
        "businessUnit"
      );

      if (!confirmed) {
        this.selectedBusinessUnits = previousState;
      } else {
        this.updateBusinessUnitDisplay();
        this.updateCustomerOptions();
        const filteredCustomers = this.getFilteredCustomers();
        if (filteredCustomers.length > 0) {
          this.selectedCustomers = [filteredCustomers[0].PrismCustomerGroup];
        } else {
          this.selectedCustomers = [];
        }
        this.updateCustomerDisplay();
      }
    },
    getFilteredCustomers() {
      if (
        this.selectedBusinessUnits.length > 0 &&
        this.selectedBusinessUnits.length < this.businessUnits.length
      ) {
        return this.customers.filter((customerObj) =>
          this.selectedBusinessUnits.includes(customerObj.FinalBU)
        );
      }
      return this.customers;
    },

    toggleBusinessUnit(bu, isChecked) {
      if (isChecked) {
        if (!this.selectedBusinessUnits.includes(bu)) {
          this.selectedBusinessUnits.push(bu);
        }
      } else {
        this.selectedBusinessUnits = this.selectedBusinessUnits.filter(
          (b) => b !== bu
        );
      }

      this.updateBusinessUnitDisplay();
      this.updateFilters();
    },

    updateBusinessUnitDisplay() {
      const displayElement = document.getElementById("bu-display");
      if (!displayElement) return;

      if (this.selectedBusinessUnits.length === 0) {
        displayElement.textContent = "Select Business Unit";
      } else {
        displayElement.textContent = this.selectedBusinessUnits[0];
      }
    },

    // Customer Methods (Enhanced)
    updateCustomerOptions() {
      const customerOptions = document.getElementById("customer-options");
      if (customerOptions) {
        // Filter customers based on selected business units
        const filteredCustomers = this.getFilteredCustomers();

        customerOptions.innerHTML = filteredCustomers
          .map(
            (customerObj) => `
        <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
          <input
            type="radio"
            name="customer-selection"
            value="${customerObj.PrismCustomerGroup}"
            class="mr-3 h-4 w-4 border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500"
            onchange="selectCustomerWithConfirmation('${
              customerObj.PrismCustomerGroup
            }')"
            ${
              this.selectedCustomers.includes(customerObj.PrismCustomerGroup)
                ? "checked"
                : ""
            }
          >
          <span class="truncate">${customerObj.PrismCustomerGroup}</span>
        </label>
      `
          )
          .join("");

        this.updateCustomerDisplay();
      }
    },

    async selectCustomerWithConfirmation(customer) {
      const previousCustomer = this.selectedCustomers[0] || null;
      this.selectedCustomers = [customer];

      const confirmed = await this.updateFiltersWithConfirmation("customer");

      if (!confirmed) {
        this.selectedCustomers = previousCustomer ? [previousCustomer] : [];
        this.updateCustomerOptions(); // Re-render radio buttons
      } else {
        this.updateCustomerDisplay();
      }
    },

    toggleCustomer(customer, isChecked) {
      if (isChecked) {
        if (!this.selectedCustomers.includes(customer)) {
          this.selectedCustomers.push(customer);
        }
      } else {
        this.selectedCustomers = this.selectedCustomers.filter(
          (c) => c !== customer
        );
      }

      this.updateCustomerDisplay();
      this.updateFilters();
    },

    updateCustomerDisplay() {
      const displayElement = document.getElementById("customer-display");
      if (!displayElement) return;

      if (this.selectedCustomers.length === 0) {
        displayElement.textContent = "Select Customer";
      } else {
        displayElement.textContent = this.selectedCustomers[0];
      }
    },

    // Location Methods (No confirmation needed as these don't reset data)
    updateLocationOptions() {
      const locationOptions = document.getElementById("location-options");
      if (locationOptions) {
        locationOptions.innerHTML = this.availableLocations
          .map(
            (location) => `
                <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
                    <input
                        type="checkbox"
                        value="${location}"
                        class="location-checkbox mr-3 h-4 w-4 rounded border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500 focus:ring-2"
                        onchange="toggleLocation('${location}', this.checked)"
                        ${
                          this.selectedLocations.includes(location)
                            ? "checked"
                            : ""
                        }
                    >
                    <span class="truncate">${location}</span>
                </label>
            `
          )
          .join("");

        this.updateLocationDisplay();
      }
    },

    toggleLocation(location, isChecked) {
      if (isChecked) {
        if (!this.selectedLocations.includes(location)) {
          this.selectedLocations.push(location);
        }
      } else {
        this.selectedLocations = this.selectedLocations.filter(
          (l) => l !== location
        );
      }

      this.updateLocationDisplay();
      this.updateSelectAllLocationState();
      this.updateFilters();
    },

    toggleAllLocations(selectAll) {
      if (selectAll) {
        this.selectedLocations = [...this.availableLocations];
      } else {
        this.selectedLocations = [];
      }

      document.querySelectorAll(".location-checkbox").forEach((checkbox) => {
        checkbox.checked = selectAll;
      });

      this.updateLocationDisplay();
      this.updateFilters();
    },

    updateSelectAllLocationState() {
      const selectAllCheckbox = document.getElementById("select-all-locations");
      if (!selectAllCheckbox) return;

      const allSelected =
        this.selectedLocations.length === this.availableLocations.length;
      const noneSelected = this.selectedLocations.length === 0;

      selectAllCheckbox.checked = allSelected;
      selectAllCheckbox.indeterminate = !allSelected && !noneSelected;
    },

    updateLocationDisplay() {
      const displayElement = document.getElementById("location-display");
      const clearButton = document.getElementById("clear-location");

      if (!displayElement) return;

      if (this.selectedLocations.length === 0) {
        displayElement.textContent = "No Locations";
        if (clearButton) clearButton.classList.remove("hidden");
      } else if (
        this.selectedLocations.length === this.availableLocations.length
      ) {
        displayElement.textContent = `All Locations (${this.availableLocations.length})`;
        if (clearButton) clearButton.classList.add("hidden");
      } else if (this.selectedLocations.length === 1) {
        displayElement.textContent = this.selectedLocations[0];
        if (clearButton) clearButton.classList.remove("hidden");
      } else {
        displayElement.textContent = `${this.selectedLocations.length} Locations`;
        if (clearButton) clearButton.classList.remove("hidden");
      }
    },

    // Billable Status Methods (No confirmation needed as these don't reset data)
    updateBillableOptions() {
      const billableOptions = document.getElementById("billable-options");
      if (billableOptions) {
        billableOptions.innerHTML = this.availableBillableStatus
          .map(
            (status) => `
                <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
                    <input
                        type="checkbox"
                        value="${status.value}"
                        class="billable-checkbox mr-3 h-4 w-4 rounded border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500 focus:ring-2"
                        onchange="toggleBillableStatus('${
                          status.value
                        }', this.checked)"
                        ${
                          this.selectedBillableStatus.includes(status.value)
                            ? "checked"
                            : ""
                        }
                    >
                    <span class="truncate">${status.label}</span>
                </label>
            `
          )
          .join("");

        this.updateBillableDisplay();
      }
    },

    toggleBillableStatus(statusValue, isChecked) {
      if (isChecked) {
        if (!this.selectedBillableStatus.includes(statusValue)) {
          this.selectedBillableStatus.push(statusValue);
        }
      } else {
        this.selectedBillableStatus = this.selectedBillableStatus.filter(
          (s) => s !== statusValue
        );
      }

      this.updateBillableDisplay();
      this.updateSelectAllBillableState();
      this.updateFilters();
    },

    toggleAllBillableStatus(selectAll) {
      if (selectAll) {
        this.selectedBillableStatus = [
          ...this.availableBillableStatus.map((s) => s.value),
        ];
      } else {
        this.selectedBillableStatus = [];
      }

      document.querySelectorAll(".billable-checkbox").forEach((checkbox) => {
        checkbox.checked = selectAll;
      });

      this.updateBillableDisplay();
      this.updateFilters();
    },

    updateSelectAllBillableState() {
      const selectAllCheckbox = document.getElementById("select-all-billable");
      if (!selectAllCheckbox) return;

      const allSelected =
        this.selectedBillableStatus.length ===
        this.availableBillableStatus.length;
      const noneSelected = this.selectedBillableStatus.length === 0;

      selectAllCheckbox.checked = allSelected;
      selectAllCheckbox.indeterminate = !allSelected && !noneSelected;
    },

    updateBillableDisplay() {
      const displayElement = document.getElementById("billable-display");
      const clearButton = document.getElementById("clear-billable");

      if (!displayElement) return;

      if (this.selectedBillableStatus.length === 0) {
        displayElement.textContent = "No Billability";
        if (clearButton) clearButton.classList.remove("hidden");
      } else if (
        this.selectedBillableStatus.length ===
        this.availableBillableStatus.length
      ) {
        displayElement.textContent = `All Billability (${this.availableBillableStatus.length})`;
        if (clearButton) clearButton.classList.add("hidden");
      } else if (this.selectedBillableStatus.length === 1) {
        const selectedStatus = this.availableBillableStatus.find(
          (s) => s.value === this.selectedBillableStatus[0]
        );
        displayElement.textContent = selectedStatus
          ? selectedStatus.label
          : this.selectedBillableStatus[0];
        if (clearButton) clearButton.classList.remove("hidden");
      } else {
        displayElement.textContent = `${this.selectedBillableStatus.length} Selected`;
        if (clearButton) clearButton.classList.remove("hidden");
      }
    },

    // Single select methods (Enhanced for month selection)
    async selectMonth(monthKey, monthDisplay = null) {
      // Store previous state
      const previousMonth = this.month;

      // Apply the change temporarily
      this.month = monthKey;
      const displayText = monthDisplay || monthKey;
      const displayElement = document.getElementById("month-display");
      if (displayElement) {
        displayElement.textContent = displayText;
      }

      // Check for confirmation if needed
      const confirmed = await this.updateFiltersWithConfirmation("month");

      if (!confirmed) {
        // Revert the change
        this.month = previousMonth;
        this.updateMonthDisplay();
      }
    },

    // API Methods
    updateFilters() {
      const queryParams = new URLSearchParams({
        month: this.month,
        businessUnits: this.selectedBusinessUnits.join(","),
        customers: this.selectedCustomers.join(","),
        locations: this.selectedLocations.join(","),
        billableStatus: this.selectedBillableStatus.join(","),
      });

      if (typeof updateFilteredGMData === "function") {
        updateFilteredGMData();
      }

      fetch(`/api/employees?${queryParams}`)
        .then((res) => res.json())
        .then((data) => {
          Alpine.store("employees").setFilteredEmployees(data);
        });
    },
  });
});

function selectCustomerWithConfirmation(customer) {
  Alpine.store("filters").selectCustomerWithConfirmation(customer);
}

function selectBusinessUnitWithConfirmation(bu) {
  Alpine.store("filters").selectBusinessUnitWithConfirmation(bu);
}
