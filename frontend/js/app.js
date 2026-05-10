// ======================================
// API CONFIG
// ======================================

const API_BASE_URL =
"http://127.0.0.1:8000/api/v1";

// ======================================
// DEMO CREDENTIALS
// ======================================
const DEMO_EMAIL =
"hr@example.com";

const DEMO_PASSWORD =
"Hr@Admin123";

// ======================================
// TOKEN HELPERS
// ======================================

function getToken() {
return localStorage.getItem(
"access_token"
);
}

function saveToken(token) {
localStorage.setItem(
"access_token",
token
);
}

function logout() {


localStorage.removeItem(
    "access_token"
);

localStorage.removeItem(
    "refresh_token"
);

window.location.href =
    "index.html";


}

// ======================================
// COMMON API FETCH
// ======================================

async function apiFetch(
endpoint,
method = "GET",
body = null
) {


const options = {

    method: method,

    headers: {
        "Content-Type":
            "application/json",

        "Authorization":
            `Bearer ${getToken()}`
    }
};

if (body) {
    options.body =
        JSON.stringify(body);
}

const response =
    await fetch(
        `${API_BASE_URL}${endpoint}`,
        options
    );

if (!response.ok) {

    console.error(
        "API ERROR:",
        response.status
    );

    throw new Error(
        "API request failed"
    );
}

return await response.json();


}

// ======================================
// LOGIN HANDLER
// ======================================

const loginForm =
document.getElementById(
"loginForm"
);

if (loginForm) {


loginForm.addEventListener(
    "submit",
    async (e) => {

        e.preventDefault();

        const email =
            document.getElementById(
                "email"
            ).value;

        const password =
            document.getElementById(
                "password"
            ).value;

        // ======================================
        // DEMO LOGIN
        // ======================================

        if (
            email === DEMO_EMAIL &&
            password === DEMO_PASSWORD
        ) {

            saveToken(
                "demo-access-token"
            );

            localStorage.setItem(
                "demo_mode",
                "true"
            );

            alert(
                "Demo login successful"
            );

            window.location.href =
                "dashboard.html";

            return;
        }

        // ======================================
        // REAL BACKEND LOGIN
        // ======================================

        try {

            const response =
                await fetch(
                    `${API_BASE_URL}/auth/login/`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            username: email,
                            password: password
                        })
                    }
                );

            const data =
                await response.json();

            console.log(
                "LOGIN RESPONSE:",
                data
            );

            if (response.ok) {

                saveToken(
                    data.access
                );

                localStorage.setItem(
                    "refresh_token",
                    data.refresh
                );

                localStorage.setItem(
                    "demo_mode",
                    "false"
                );

                alert(
                    "Backend login successful"
                );

                window.location.href =
                    "dashboard.html";

            } else {

                alert(
                    data.detail ||
                    "Invalid credentials"
                );
            }

        } catch (error) {

            console.error(error);

            alert(
                "Backend connection failed"
            );
        }
    }
);


}

// ======================================
// LOAD DASHBOARD STATS
// ======================================

async function loadDashboard() {


const employeeCount =
    document.getElementById(
        "employeeCount"
    );

if (!employeeCount) return;

try {

    const employees =
        await apiFetch(
            "/employees/"
        );

    const leaves =
        await apiFetch(
            "/leave-requests/"
        );

    const uploads =
        await apiFetch(
            "/bulk-uploads/"
        );

    employeeCount.innerText =
        employees.count ||
        employees.length ||
        0;

    document.getElementById(
        "leaveCount"
    ).innerText =
        leaves.count ||
        leaves.length ||
        0;

    document.getElementById(
        "uploadCount"
    ).innerText =
        uploads.count ||
        uploads.length ||
        0;

} catch (error) {

    console.error(error);
}


}

// ======================================
// LOAD EMPLOYEES
// ======================================

async function loadEmployees() {


const tableBody =
    document.getElementById(
        "employeeTableBody"
    );

if (!tableBody) return;

try {

    const data =
        await apiFetch(
            "/employees/"
        );

    const employees =
        data.results || data;

    tableBody.innerHTML = "";

    employees.forEach(employee => {

        const row = `
            <tr>

                <td>
                    ${employee.full_name || "-"}
                </td>

                <td>
                    ${employee.department || "-"}
                </td>

                <td>
                    ${employee.email || "-"}
                </td>

                <td>
                    <span class="badge success">
                        Active
                    </span>
                </td>

                <td>
                    ${employee.role || "-"}
                </td>

            </tr>
        `;

        tableBody.innerHTML += row;
    });

} catch (error) {

    console.error(error);

    tableBody.innerHTML = `
        <tr>
            <td colspan="5">
                Failed to load employees
            </td>
        </tr>
    `;
}


}

// ======================================
// LOAD LEAVES
// ======================================

async function loadLeaves() {


const tableBody =
    document.getElementById(
        "leaveTableBody"
    );

if (!tableBody) return;

try {

    const data =
        await apiFetch(
            "/leave-requests/"
        );

    const leaves =
        data.results || data;

    tableBody.innerHTML = "";

    leaves.forEach(leave => {

        const row = `
            <tr>

                <td>
                    ${leave.employee || "-"}
                </td>

                <td>
                    ${leave.leave_type || "-"}
                </td>

                <td>
                    ${leave.duration_days || "-"}
                </td>

                <td>
                    <span class="badge warning">
                        ${leave.status || "-"}
                    </span>
                </td>

                <td>

                    <button
                        class="table-btn approve"
                    >
                        Approve
                    </button>

                    <button
                        class="table-btn reject"
                    >
                        Reject
                    </button>

                </td>

            </tr>
        `;

        tableBody.innerHTML += row;
    });

} catch (error) {

    console.error(error);
}


}

// ======================================
// LOAD AUDIT LOGS
// ======================================

async function loadAuditLogs() {


const timeline =
    document.getElementById(
        "auditTimeline"
    );

if (!timeline) return;

try {

    const data =
        await apiFetch(
            "/audit-logs/"
        );

    const logs =
        data.results || data;

    timeline.innerHTML = "";

    logs.forEach(log => {

        const item = `
            <div class="timeline-item">

                <div class="timeline-dot"></div>

                <div class="timeline-content">

                    <h3>
                        ${log.action || "-"}
                    </h3>

                    <p>
                        ${log.description || "-"}
                    </p>

                    <span>
                        ${log.created_at || "-"}
                    </span>

                </div>

            </div>
        `;

        timeline.innerHTML += item;
    });

} catch (error) {

    console.error(error);
}


}

// ======================================
// PAGE INITIALIZATION
// ======================================

document.addEventListener(
"DOMContentLoaded",
() => {

    loadDashboard();

    loadEmployees();

    loadLeaves();

    loadAuditLogs();
}


);
