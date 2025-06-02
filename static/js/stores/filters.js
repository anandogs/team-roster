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

    // Initialization
    async init() {
      const [filterResponse, periodResponse, customersResponse] =
        await Promise.all([
          fetch("/api/filter-state"),
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
        if (!seenCustomers.has(c.FinalCustomer)) {
          seenCustomers.add(c.FinalCustomer);
          uniqueCustomers.push({
            FinalCustomer: c.FinalCustomer,
            FinalBU: c.FinalBU,
          });
        }
      });
      this.customers = uniqueCustomers;

      this.selectedCustomers = [...this.customers];
      this.selectedLocations = [...this.availableLocations];
      this.selectedBillableStatus = [
        ...this.availableBillableStatus.map((s) => s.value),
      ];
      this.selectedBusinessUnits = [...this.businessUnits];

      if (periodData.QTR) {
        document.querySelector(".bg-neutral-800 .text-white").textContent =
          periodData.QTR;
      }

      this.populateOptions();

      setTimeout(() => {
        this.populateOptions();
      }, 1000);
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

    // Business Unit Methods
    updateBusinessUnitOptions() {
      const buOptions = document.getElementById("bu-options");
      if (buOptions) {
        buOptions.innerHTML = this.businessUnits
          .map(
            (bu) => `
                <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
                    <input
                        type="checkbox"
                        value="${bu}"
                        class="bu-checkbox mr-3 h-4 w-4 rounded border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500 focus:ring-2"
                        onchange="toggleBusinessUnit('${bu}', this.checked)"
                        ${
                          this.selectedBusinessUnits.includes(bu)
                            ? "checked"
                            : ""
                        }
                    >
                    <span class="truncate">${bu}</span>
                </label>
            `
          )
          .join("");

        this.updateBusinessUnitDisplay();
      }
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
      this.updateSelectAllBusinessUnitState();
      this.updateFilters();
    },

    toggleAllBusinessUnits(selectAll) {
      if (selectAll) {
        this.selectedBusinessUnits = [...this.businessUnits];
      } else {
        this.selectedBusinessUnits = [];
      }

      document.querySelectorAll(".bu-checkbox").forEach((checkbox) => {
        checkbox.checked = selectAll;
      });

      this.updateBusinessUnitDisplay();
      this.updateFilters();
    },

    updateSelectAllBusinessUnitState() {
      const selectAllCheckbox = document.getElementById(
        "select-all-business-units"
      );
      if (!selectAllCheckbox) return;

      const allSelected =
        this.selectedBusinessUnits.length === this.businessUnits.length;
      const noneSelected = this.selectedBusinessUnits.length === 0;

      selectAllCheckbox.checked = allSelected;
      selectAllCheckbox.indeterminate = !allSelected && !noneSelected;
    },

    updateBusinessUnitDisplay() {
      const displayElement = document.getElementById("bu-display");
      const clearButton = document.getElementById("clear-bu");

      if (!displayElement) return;

      if (this.selectedBusinessUnits.length === 0) {
        displayElement.textContent = "No Business Units";
        if (clearButton) clearButton.classList.remove("hidden");
      } else if (
        this.selectedBusinessUnits.length === this.businessUnits.length
      ) {
        displayElement.textContent = `All Business Units (${this.businessUnits.length})`;
        if (clearButton) clearButton.classList.add("hidden");
      } else if (this.selectedBusinessUnits.length === 1) {
        displayElement.textContent = this.selectedBusinessUnits[0];
        if (clearButton) clearButton.classList.remove("hidden");
      } else {
        displayElement.textContent = `${this.selectedBusinessUnits.length} Business Units`;
        if (clearButton) clearButton.classList.remove("hidden");
      }
    },

    clearAllBusinessUnits() {
      this.selectedBusinessUnits = [];

      document.querySelectorAll(".bu-checkbox").forEach((checkbox) => {
        checkbox.checked = false;
      });

      const selectAllCheckbox = document.getElementById(
        "select-all-business-units"
      );
      if (selectAllCheckbox) selectAllCheckbox.checked = false;

      this.updateBusinessUnitDisplay();
      this.updateFilters();
    },

    // Customer Methods
    updateCustomerOptions() {
      const customerOptions = document.getElementById("customer-options");
      if (customerOptions) {
        customerOptions.innerHTML = this.customers
          .map(
            (customerObj) => `
    <label class="flex items-center px-2 py-1.5 text-sm text-white hover:bg-neutral-700 rounded-sm cursor-pointer">
        <input
            type="checkbox"
            value="${customerObj.FinalCustomer}"
            class="customer-checkbox mr-3 h-4 w-4 rounded border-neutral-600 bg-neutral-700 text-blue-600 focus:ring-blue-500 focus:ring-2"
            onchange="toggleCustomer('${
              customerObj.FinalCustomer
            }', this.checked)"
            ${
              this.selectedCustomers.includes(customerObj.FinalCustomer)
                ? "checked"
                : ""
            }
        >
        <span class="truncate">${customerObj.FinalCustomer}</span>
    </label>
            `
          )
          .join("");

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
      this.updateSelectAllState();
      this.updateFilters();
    },

    toggleAllCustomers(selectAll) {
      if (selectAll) {
        this.selectedCustomers = [...this.customers];
      } else {
        this.selectedCustomers = [];
      }

      document.querySelectorAll(".customer-checkbox").forEach((checkbox) => {
        checkbox.checked = selectAll;
      });

      this.updateCustomerDisplay();
      this.updateFilters();
    },

    updateSelectAllState() {
      const selectAllCheckbox = document.getElementById("select-all-customers");
      if (!selectAllCheckbox) return;

      const allSelected =
        this.selectedCustomers.length === this.customers.length;
      const noneSelected = this.selectedCustomers.length === 0;

      selectAllCheckbox.checked = allSelected;
      selectAllCheckbox.indeterminate = !allSelected && !noneSelected;
    },

    updateCustomerDisplay() {
      const displayElement = document.getElementById("customer-display");
      const clearButton = document.getElementById("clear-customer");

      if (!displayElement) return;

      if (this.selectedCustomers.length === 0) {
        displayElement.textContent = "No Customers";
        if (clearButton) clearButton.classList.remove("hidden");
      } else if (this.selectedCustomers.length === this.customers.length) {
        displayElement.textContent = `All Customers (${this.customers.length})`;
        if (clearButton) clearButton.classList.add("hidden");
      } else if (this.selectedCustomers.length === 1) {
        displayElement.textContent = this.selectedCustomers[0];
        if (clearButton) clearButton.classList.remove("hidden");
      } else {
        displayElement.textContent = `${this.selectedCustomers.length} Customers`;
        if (clearButton) clearButton.classList.remove("hidden");
      }
    },

    clearAllCustomers() {
      this.selectedCustomers = [];

      document.querySelectorAll(".customer-checkbox").forEach((checkbox) => {
        checkbox.checked = false;
      });

      const selectAllCheckbox = document.getElementById("select-all-customers");
      if (selectAllCheckbox) selectAllCheckbox.checked = false;

      this.updateCustomerDisplay();
      this.updateFilters();
    },

    // Location Methods
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

    clearAllLocations() {
      this.selectedLocations = [];

      document.querySelectorAll(".location-checkbox").forEach((checkbox) => {
        checkbox.checked = false;
      });

      const selectAllCheckbox = document.getElementById("select-all-locations");
      if (selectAllCheckbox) selectAllCheckbox.checked = false;

      this.updateLocationDisplay();
      this.updateFilters();
    },

    // Billable Status Methods
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

    clearAllBillableStatus() {
      this.selectedBillableStatus = [];

      document.querySelectorAll(".billable-checkbox").forEach((checkbox) => {
        checkbox.checked = false;
      });

      const selectAllCheckbox = document.getElementById("select-all-billable");
      if (selectAllCheckbox) selectAllCheckbox.checked = false;

      this.updateBillableDisplay();
      this.updateFilters();
    },

    // Single select methods
    selectMonth(monthKey, monthDisplay = null) {
      this.month = monthKey;
      const displayText = monthDisplay || monthKey;
      const displayElement = document.getElementById("month-display");
      if (displayElement) {
        displayElement.textContent = displayText;
      }
      this.updateFilters();
    },

    selectBusinessUnit(bu) {
      this.businessUnit = bu;
      const displayElement = document.getElementById("bu-display");
      const clearButton = document.getElementById("clear-bu");

      if (displayElement) displayElement.textContent = bu;
      if (clearButton) clearButton.classList.remove("hidden");

      this.updateFilters();
    },

    clearBusinessUnit() {
      this.businessUnit = "";
      const displayElement = document.getElementById("bu-display");
      const clearButton = document.getElementById("clear-bu");

      if (displayElement) displayElement.textContent = "BU";
      if (clearButton) clearButton.classList.add("hidden");

      this.clearAllCustomers();
      this.updateFilters();
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

      fetch(`/api/gm-state?${queryParams}`)
        .then((res) => res.json())
        .then((data) => {
          if (typeof updateGMSummary === "function") {
            updateGMSummary();
          }
        });

      fetch(`/api/employees?${queryParams}`)
        .then((res) => res.json())
        .then((data) => {
          Alpine.store("employees").setFilteredEmployees(data);
        });
    },
  });
});
