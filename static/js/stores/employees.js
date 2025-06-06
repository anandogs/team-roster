// Employees Store
document.addEventListener("alpine:init", () => {
  Alpine.store("employees", {
    totalEmployees: [],
    baseRosterEmployees: [],
    newHires: [],
    loading: true,
    auditLogVersion: 0,

    get rosterEmployees() {
      this.auditLogVersion;
      return this.applyAuditLog(this.baseRosterEmployees, this.auditLog);
    },

    get auditLog() {
      const stored = localStorage.getItem("roster-audit-log");
      return stored ? JSON.parse(stored) : [];
    },

    async init() {
      this.loading = true;
      await Promise.all([
        this.loadTotalEmployees(),
        this.loadRosterEmployees(),
      ]);
      this.loading = false;
      this.notifyStateChange();
    },

    async loadTotalEmployees() {
      try {
        const response = await fetch("/api/total-employees");
        this.totalEmployees = await response.json();
      } catch (e) {
        this.totalEmployees = [];
      }
    },

    async loadRosterEmployees() {
      try {
        const response = await fetch("/api/employees");
        const data = await response.json();
        this.baseRosterEmployees = data;
      } catch (e) {
        this.baseRosterEmployees = [];
      }
    },

    applyAuditLog(baseEmployees, auditLog) {
      let result = [...baseEmployees];

      auditLog.forEach((entry) => {
        if (entry.action === "EDIT_FTE") {
          const empIndex = result.findIndex(
            (emp) => emp.id === entry.employeeId
          );
          if (empIndex !== -1) {
            result[empIndex] = {
              ...result[empIndex],
              FTE: entry.newValue,
            };
          }
        } else if (entry.action === "REMOVE_EMPLOYEE") {
          result = result.filter((emp) => emp.id !== entry.employeeId);
        } else if (entry.action === "ADD_EMPLOYEE") {
          // Add the new employee if not already present
          const exists = result.some((emp) => emp.id === entry.employeeId);
          if (!exists && entry.employeeData) {
            result.unshift(entry.employeeData); // Use unshift() instead of push() to add at the beginning
          }
        }
      });

      return result;
    },

    async addAuditEntry(
      action,
      employeeId,
      oldValue,
      newValue,
      employeeName,
      employeeData = null
    ) {
      const entry = {
        id: `audit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date().toISOString(),
        action,
        employeeId,
        oldValue,
        newValue,
        employeeName,
        description: this.getAuditDescription(
          action,
          employeeName,
          oldValue,
          newValue
        ),
      };

      // Add employee data for ADD_EMPLOYEE actions
      if (action === "ADD_EMPLOYEE" && employeeData) {
        entry.employeeData = employeeData;
      }

      // For GM impact calculation, we need additional data
      let gmCalculationData = {
        action,
        employeeId,
        employeeName,
        oldValue: parseFloat(oldValue) || 0,
        newValue: parseFloat(newValue) || 0,
        fteChange: (parseFloat(newValue) || 0) - (parseFloat(oldValue) || 0),
      };

      // Get additional employee details based on action type
      if (action === "ADD_EMPLOYEE" && employeeData) {
        // For both existing employees and new hires
        gmCalculationData.employeeCode =
          employeeData.EmployeeCode || employeeData.id;
        gmCalculationData.band = employeeData.Band;
        gmCalculationData.location = employeeData.Offshore_Onsite;
        gmCalculationData.isNewHire = String(employeeData.id || "").startsWith(
          "newhire"
        );
        gmCalculationData.billableYN = employeeData.BillableYN;
        gmCalculationData.finalBU = employeeData.FinalBU;
        gmCalculationData.PrismCustomerGroup = employeeData.PrismCustomerGroup;
      } else {
        // For EDIT_FTE and REMOVE_EMPLOYEE, look up employee details
        const employee = this.findEmployeeDetails(employeeId);
        if (employee) {
          gmCalculationData.employeeCode = employee.EmployeeCode || employee.id;
          gmCalculationData.band = employee.Band;
          gmCalculationData.location = employee.Offshore_Onsite;
          gmCalculationData.isNewHire = String(employee.id || "").startsWith(
            "newhire"
          );
          gmCalculationData.billableYN = employee.BillableYN;
          gmCalculationData.finalBU = employee.FinalBU;
          gmCalculationData.PrismCustomerGroup = employee.PrismCustomerGroup;
        }
      }

      // Add GM calculation data to entry
      entry.gmData = gmCalculationData;

      const currentLog = this.auditLog;
      currentLog.push(entry);

      try {
        const response = await fetch("/api/gm-impact", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            auditLog: currentLog,
            latestEntry: entry,
          }),
        });

        if (response.ok) {
          const gmResult = await response.json();

          // Use the updated audit log with GM impact data
          const updatedAuditLog = gmResult.auditLog || currentLog;
          localStorage.setItem(
            "roster-audit-log",
            JSON.stringify(updatedAuditLog)
          );

          // Log the GM impact for the latest entry
          const latestEntryWithGM = updatedAuditLog[updatedAuditLog.length - 1];
          if (latestEntryWithGM?.gmImpact) {
            console.log("GM Impact calculated:");
          }
        } else {
          console.error("GM impact calculation failed:", response.status);
          // Fallback: save without GM impact
          localStorage.setItem("roster-audit-log", JSON.stringify(currentLog));
        }
      } catch (error) {
        console.error("Error calling GM impact calculation:", error);
        // Fallback: save without GM impact
        localStorage.setItem("roster-audit-log", JSON.stringify(currentLog));
      }

      this.auditLogVersion++;
      window.dispatchEvent(new CustomEvent("audit-log-updated"));
      this.notifyStateChange();
    },

    // Add this helper method to find employee details
    findEmployeeDetails(employeeId) {
      // First check in base roster employees
      let employee = this.baseRosterEmployees.find(
        (emp) => emp.id === employeeId
      );

      // If not found, check in new hires
      if (!employee) {
        employee = this.newHires.find((emp) => emp.id === employeeId);
      }

      // If still not found, check in total employees pool
      if (!employee) {
        employee = this.totalEmployees.find(
          (emp) => (emp.EmployeeCode || emp.id) === employeeId
        );
      }

      return employee;
    },

    getAuditDescription(action, employeeName, oldValue, newValue) {
      if (action === "EDIT_FTE") {
        return `${employeeName}: FTE changed from ${oldValue} to ${newValue}`;
      } else if (action === "REMOVE_EMPLOYEE") {
        return `${employeeName}: Removed from roster (FTE: ${oldValue} > 0)`;
      } else if (action === "ADD_EMPLOYEE") {
        return `${employeeName}: Added to roster (FTE: 0 > ${newValue})`;
      }
      return "";
    },

    clearAuditLog() {
      localStorage.removeItem("roster-audit-log");
      this.auditLogVersion++;
      window.dispatchEvent(new CustomEvent("audit-log-updated"));
    },

    getAvailableEmployees() {
      const rosterIds = new Set([
        ...this.rosterEmployees.map((emp) => emp.id),
        ...this.newHires.map((emp) => emp.id),
      ]);
      return this.totalEmployees.filter((emp) => !rosterIds.has(emp.id));
    },

    addToRoster(employee, fte, location, isBillable) {
      const rosterEmployee = {
        ...employee,
        fte: parseFloat(fte),
        location,
        isBillable,
      };

      this.baseRosterEmployees.push(rosterEmployee);
      this.notifyStateChange();
    },

    setFilteredEmployees(data) {
      this.baseRosterEmployees = [...data];
      this.notifyStateChange();
    },

    removeFromRoster(employeeId) {
      // First check in baseRosterEmployees
      let employee = this.baseRosterEmployees.find(
        (emp) => emp.id === employeeId
      );

      // If not found, check in the rendered roster (which includes audit log applied)
      if (!employee) {
        employee = this.rosterEmployees.find((emp) => emp.id === employeeId);
      }

      if (employee) {
        const currentFTE = employee.FTE || 0;

        this.addAuditEntry(
          "REMOVE_EMPLOYEE",
          employeeId,
          currentFTE,
          0,
          employee.EmployeeName
        );
      } else {
        console.warn("Employee not found for removal:", employeeId);
      }
    },

    updateEmployeeFTE(employeeId, oldFTE, newFTE) {
      const employee = this.baseRosterEmployees.find(
        (emp) => emp.id === employeeId
      );
      if (employee) {
        this.addAuditEntry(
          "EDIT_FTE",
          employeeId,
          oldFTE,
          newFTE,
          employee.EmployeeName
        );
      }
    },

    addNewHire(newHire) {
      const id = `newhire${this.newHires.length + 1}`;
      this.newHires.push({ ...newHire, id });
      this.notifyStateChange();
    },

    notifyStateChange() {
      window.dispatchEvent(new CustomEvent("employees-updated"));
    },
  });
});
