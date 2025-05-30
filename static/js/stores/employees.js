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
        const stored = localStorage.getItem('roster-audit-log');
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
        
        auditLog.forEach(entry => {
            if (entry.action === 'EDIT_FTE') {
                const empIndex = result.findIndex(emp => emp.id === entry.employeeId);
                if (empIndex !== -1) {
                    result[empIndex] = {
                        ...result[empIndex],
                        FTE: entry.newValue
                    };
                }
            } else if (entry.action === 'REMOVE_EMPLOYEE') {
                result = result.filter(emp => emp.id !== entry.employeeId);
            }
        });
        
        return result;
    },

    addAuditEntry(action, employeeId, oldValue, newValue, employeeName) {
        const entry = {
            id: `audit_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: new Date().toISOString(),
            action,
            employeeId,
            oldValue,
            newValue,
            employeeName,
            description: this.getAuditDescription(action, employeeName, oldValue, newValue)
        };

        const currentLog = this.auditLog;
        currentLog.push(entry);
        localStorage.setItem('roster-audit-log', JSON.stringify(currentLog));
        
        this.auditLogVersion++;
        window.dispatchEvent(new CustomEvent('audit-log-updated'));
        this.notifyStateChange();
    },

    getAuditDescription(action, employeeName, oldValue, newValue) {
        if (action === 'EDIT_FTE') {
            return `${employeeName}: FTE changed from ${oldValue} to ${newValue}`;
        } else if (action === 'REMOVE_EMPLOYEE') {
            return `${employeeName}: Removed from roster`;
        }
        return '';
    },

    clearAuditLog() {
        localStorage.removeItem('roster-audit-log');
        this.auditLogVersion++;
        window.dispatchEvent(new CustomEvent('audit-log-updated'));
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
        const employee = this.baseRosterEmployees.find(emp => emp.id === employeeId);
        if (employee) {
            this.addAuditEntry('REMOVE_EMPLOYEE', employeeId, null, null, employee.EmployeeName);
        }
    },

    updateEmployeeFTE(employeeId, oldFTE, newFTE) {
        const employee = this.baseRosterEmployees.find(emp => emp.id === employeeId);
        if (employee) {
            this.addAuditEntry('EDIT_FTE', employeeId, oldFTE, newFTE, employee.EmployeeName);
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