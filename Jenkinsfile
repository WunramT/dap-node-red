pipeline {
    agent any

    parameters {
        choice(name: 'TARGET_SERVER', choices: ['cho-svr-lin01', 'pod-svr-lin01', 'jan-svr-lin01', 'srem-svr-lin01', 'foi-svr-lnx01', 'wag-svr-lin01', 'gor-svr-lin01', 'slu-svr-lin02'], description: 'Server to deploy to')
        choice(name: 'ENVIRONMENT', choices: ['test', 'prod'], description: 'Target environment')
        choice(name: 'COPY_PROD_SCHEMA', choices: ['no', 'yes'], description: 'Copy production database schema to test environment?')
        string(name: 'IMAGE_TAG_FRONTEND', defaultValue: 'latest', description: 'Docker image tag to deploy')
        string(name: 'IMAGE_TAG_BACKEND', defaultValue: 'latest', description: 'Docker image tag to deploy')
        string(name: 'BACKEND_HOSTNAME', defaultValue: '', description: 'Custom backend hostname (for K8s/cluster deployments). Leave empty to use container name.')
        string(name: 'FRONTEND_HOSTNAME', defaultValue: '', description: 'Custom frontend hostname (for K8s/cluster deployments). Leave empty to use container name.')
        string(name: 'DNS_RESOLVER', defaultValue: '127.0.0.11', description: 'DNS resolver (K8s: kube-dns.kube-system.svc.cluster.local)')
    }

    environment {
        PROJECT_NAME = '{{PROJECT_NAME}}'
        REGISTRY_URL = 'harbor.aks-infra.polipol-service.de'
        BACKEND_IMAGE = "${REGISTRY_URL}/dap-api/${PROJECT_NAME}"
        FRONTEND_IMAGE = "${REGISTRY_URL}/dap-ui/${PROJECT_NAME}"

        // Postgres config — used for schema backup/restore
        POSTGRES_CONTAINER_PROD = 'postgres_db_prod'
        POSTGRES_CONTAINER_TEST  = 'postgres_db_dev'
        POSTGRES_CONTAINER = "${params.ENVIRONMENT == 'prod' ? POSTGRES_CONTAINER_PROD : POSTGRES_CONTAINER_TEST}"
        POSTGRES_DB        = 'postgres'
        POSTGRES_USER      = 'postgres'
        POSTGRES_SCHEMA    = ''  // DATABASE SCHEMA (empty by default)
        HOST_BACKUP_DIR    = '~/backups'         // host path, mounted into containers
        CONTAINER_BACKUP_DIR = '/backups'            // path inside containers

        // Tracks whether alembic migration ran, so post{failure} knows whether to restore DB.
        MIGRATION_RAN = 'false'

        // Network - connect to existing app_network on host for nginx routing
        APP_NETWORK = 'app_network'

        // Container names - must match nginx.conf location blocks
        // Example Format: cparts-replenishment_frontend_prod / cparts-replenishment_backend_prod
        BACKEND_CONTAINER = "${PROJECT_NAME}_backend_${params.ENVIRONMENT}"
        FRONTEND_CONTAINER = "${PROJECT_NAME}_frontend_${params.ENVIRONMENT}"
        BACKEND_PORT = 8000

        // Deployment directory (sens.env with all secrets must exist here)
        DEPLOY_DIR = "\$HOME/deployment/${PROJECT_NAME}_${params.ENVIRONMENT}"

        // Application URL path - different for test vs prod
        APP_PATH = "${params.ENVIRONMENT == 'prod' ? '/{{PROJECT_NAME}}/' : '/test/{{PROJECT_NAME}}/'}"

        // Enable authentication for production
        ENABLE_AUTH = 'true'
    }

    stages {
        stage('Preparation') {
            steps {
                script {
                    echo "=========================================="
                    echo "Deploying ${PROJECT_NAME} to ${params.ENVIRONMENT} environment"
                    echo "=========================================="
                    echo ""
                    echo "Backend Image: ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}"
                    echo "Frontend Image: ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}"
                    echo "Config: ${DEPLOY_DIR}/base/sens.env"
                    echo "Application URL: https://iot.polipol-service.pl${APP_PATH}"
                    echo "Auth enabled: ${ENABLE_AUTH}"
                    echo ""
                    if (params.BACKEND_HOSTNAME?.trim()) {
                        echo "Custom BACKEND_HOSTNAME: ${params.BACKEND_HOSTNAME}"
                    }
                    if (params.FRONTEND_HOSTNAME?.trim()) {
                        echo "Custom FRONTEND_HOSTNAME: ${params.FRONTEND_HOSTNAME}"
                    }
                    if (params.ENVIRONMENT == 'test') {
                        echo "Database schema: ${POSTGRES_SCHEMA}"
                    }
                }
            }
        }

        stage('Set Remote Host') {
            steps {
                script {
                    // Function to create host config map for easier management
                    def mkHost = { name, ip, credId -> [name: name, host: ip, port: 22, allowAnyHosts: true, credId: credId] }

                    // Map of available hosts with credentials IDs
                    def HOSTS = [
                        'cho-svr-lin01': mkHost('cho-svr-lin01', '10.11.1.101', 'cho-svr-lin01_pw'),
                        'pod-svr-lin01': mkHost('pod-svr-lin01', '10.20.1.160', 'pod-svr-lin01_pw'),
                        'jan-svr-lin01': mkHost('jan-svr-lin01', '10.30.1.150', 'jan-svr-lin01_pw'),
                        'srem-svr-lin01': mkHost('srem-svr-lin01', '10.40.1.161', 'srem-svr-lin01_pw'),
                        'wag-svr-lin01': mkHost('wag-svr-lin01', '10.60.1.198', 'wag-svr-lin01_pw'),
                        'foi-svr-lnx01': mkHost('foi-svr-lnx01', '192.168.64.60', 'foi-svr-lnx01_pw'),
                        'gor-svr-lin01': mkHost('gor-svr-lin01', '10.87.1.150', 'gor-svr-lin01_pw'),
                        'slu-svr-lin02': mkHost('slu-svr-lin02', '10.90.1.20', 'slu-svr-lin02_pw'),
                        // add more hosts here as single lines
                    ]

                    // Validate selected target server
                    def hostConfig = HOSTS[params.TARGET_SERVER]
                    if (!hostConfig) error("Unknown target server: ${params.TARGET_SERVER}")

                    // Set REMOTE_HOST environment variable for sshCommand steps
                    withCredentials([usernamePassword(
                        credentialsId: hostConfig.credId,  // dynamic ID - works with Groovy variable [web:36]
                        usernameVariable: 'REMOTE_USR',
                        passwordVariable: 'REMOTE_PSW'
                    )]) {
                        REMOTE = [
                            name         : params.TARGET_SERVER,
                            host         : hostConfig.host,
                            port         : hostConfig.port,
                            allowAnyHosts: hostConfig.allowAnyHosts,
                            user         : REMOTE_USR,
                            password     : REMOTE_PSW
                        ]
                    }

                    // Get HOST_PREFIX for CORS and VITE_BASE_PATH
                    // Extract first 4 chars, strip trailing '-' if present
                    def prefix = params.TARGET_SERVER.take(4).replaceAll(/-$/, '')
                    env.BASE_PATH = "/app/${prefix}"
                }
            }
        }

        stage('Connect to App Network') {
            steps {
                script {
                    // Ensure containers can connect to app_network for nginx routing
                    sshCommand remote: REMOTE, command: """
                        docker network inspect ${APP_NETWORK} >/dev/null 2>&1 || {
                            echo "ERROR: ${APP_NETWORK} does not exist!"
                            echo "This network is required for nginx routing."
                            exit 1
                        }
                    """
                }
            }
        }

        stage('Pull Images') {
            steps {
                script {
                    // Pull backend image
                    sshCommand remote: REMOTE, command: """
                        docker pull ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}
                    """

                    // Pull frontend image
                    sshCommand remote: REMOTE, command: """
                        docker pull ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Backup Database Schema
        // Purpose: Create a pg_dump of the current schema BEFORE any migration.
        //          The backup filename is stored in env.DB_BACKUP_FILE so the
        //          post{failure} block can reference and restore from the exact file.
        //
        //          Why pg_dump instead of alembic downgrade for rollback?
        //          - The old container only knows migrations up to its own version.
        //          - If the new image adds migration 'abc123', the old container
        //            has no downgrade logic for it — it can never reverse it.
        //          - pg_dump captures the exact schema state independently of any
        //            container, making rollback container-agnostic.
        // ─────────────────────────────────────────────────────────────────────
        stage('Backup Database Schema') {
            steps {
                script {
                    // When COPY_PROD_SCHEMA is yes dump and restore the prod to test.
                    if (params.ENVIRONMENT == 'test' && params.COPY_PROD_SCHEMA == 'yes') {
                        echo "COPY_PROD_SCHEMA is yes — copying production schema to test environment before migration."

                        // Before that transfer roles from prod to test since dump_restore_db.sh doesn't handle roles and missing roles would cause restore to fail.

                        sshCommand remote: REMOTE, command: """
                            # Run dump_restore_db.sh in dump-restore mode to migrate roles from prod to test.
                            # '--no-confirm' skips interactive prompt (required for CI/CD).
                            ~/backups/dump_restore_db.sh \\
                                --action        dump-restore \\
                                --mode          roles-only \\
                                --src-container ${POSTGRES_CONTAINER_PROD} \\
                                --src-user      ${POSTGRES_USER} \\
                                --target-container ${POSTGRES_CONTAINER_TEST} \\
                                --target-user    ${POSTGRES_USER} \\
                                --no-confirm

                            echo "Production roles copied to test environment successfully."
                        """

                        sshCommand remote: REMOTE, command: """
                            # Run dump_restore_db.sh in dump-restore mode to copy prod schema to test.
                            # '--no-confirm' skips interactive prompt (required for CI/CD).
                            ~/backups/dump_restore_db.sh \\
                                --action        dump-restore \\
                                --mode          schema \\
                                --src-container ${POSTGRES_CONTAINER_PROD} \\
                                --src-user      ${POSTGRES_USER} \\
                                --src-db        ${POSTGRES_DB} \\
                                --src-schema    ${POSTGRES_SCHEMA} \\
                                --target-container ${POSTGRES_CONTAINER_TEST} \\
                                --target-user    ${POSTGRES_USER} \\
                                --target-db      ${POSTGRES_DB} \\
                                --target-schema  ${POSTGRES_SCHEMA} \\
                                --container-backup-dir ${CONTAINER_BACKUP_DIR} \\
                                --no-confirm

                            echo "Production schema copied to test environment successfully."
                        """

                        // No need for further backup or restore during rollback since we're copying prod schema directly to test.
                        env.MIGRATION_RAN = 'false'  // ensure no DB restore attempted during rollback
                        return  // skip the rest of this stage
                    }

                    def dumpOutput = sshCommand remote: REMOTE, command: """
                        echo "Creating schema backup before migration: ${env.DB_BACKUP_FILE}"

                        # Run dump_restore_db.sh in dump-only mode using '--mode schema'.
                        # '--no-confirm' skips the interactive confirmation prompt (required for CI/CD).
                        # The script writes the dump to ~/backups which is mounted at /backups
                        # inside the container, making it accessible from both host and container.
                        ~/backups/dump_restore_db.sh \\
                            --action        dump \\
                            --mode          schema \\
                            --src-container ${POSTGRES_CONTAINER} \\
                            --src-user      ${POSTGRES_USER} \\
                            --src-db        ${POSTGRES_DB} \\
                            --src-schema    ${POSTGRES_SCHEMA} \\
                            --container-backup-dir ${CONTAINER_BACKUP_DIR} \\
                            --no-confirm
                        """
                    // Parse the DUMP_FILE_PATH= line from script output
                    def match = (dumpOutput =~ /DUMP_FILE_PATH=(.+)/)
                    if (!match) {
                        error "Could not parse backup filename from script output!"
                    }
                    env.DB_BACKUP_FILE = match[0][1].trim()
                    echo "Backup file captured: ${env.DB_BACKUP_FILE}"
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Stop & Rename Old Containers
        // Purpose: Stop running containers and rename them to *-previous.
        //          Renaming instead of removing preserves the full 'docker run'
        //          configuration (volumes, env vars, network, restart policy)
        //          so 'docker start' can revive them identically if rollback needed.
        //
        //          Stop order: frontend first, then backend.
        //          Frontend depends on backend via Docker DNS hostname resolution.
        //          Stopping backend first would cause frontend connection errors while it is still running.
        // ─────────────────────────────────────────────────────────────────────
        stage('Stop & Rename Old Containers') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        # Stop in dependency order: frontend first, then backend
                        docker stop ${FRONTEND_CONTAINER} || true
                        docker stop ${BACKEND_CONTAINER}  || true

                        # Rename to *-previous to free the original names for new containers.
                        # 'docker inspect' checks existence first — avoids errors on first-ever deploy
                        # when no previous containers exist yet.
                        docker inspect ${BACKEND_CONTAINER} >/dev/null 2>&1 && \\
                            docker rename ${BACKEND_CONTAINER}  ${BACKEND_CONTAINER}-previous  || true
                        docker inspect ${FRONTEND_CONTAINER} >/dev/null 2>&1 && \\
                            docker rename ${FRONTEND_CONTAINER} ${FRONTEND_CONTAINER}-previous || true

                        echo "Old containers stopped and renamed to *-previous."
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Run Alembic Migration
        // Purpose: Apply new database migrations using the NEW image (which contains the new migration files) before starting the new container.
        //          We run alembic inside a temporary container that is removed after use.
        //
        //          MIGRATION_RAN is set to 'true' after success so post{failure} knows whether a DB restore is needed during rollback.
        // ─────────────────────────────────────────────────────────────────────
        stage('Run Alembic Migration') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        echo "Running alembic upgrade head using new image..."

                        # Run alembic in a temporary container ('--rm' removes it after exit).
                        # Uses the new backend image so it has all new migration files.
                        # Mounted env-file and volumes must match the main backend container.
                        docker run --rm \\
                            --network ${APP_NETWORK} \\
                            --env-file ${DEPLOY_DIR}/base/sens.env \\
                            -e DEBUG=False \\
                            -v ${DEPLOY_DIR}/logs:/app/logs \\
                            ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND} \\
                            alembic -c /app/migrations/alembic.ini upgrade head

                        echo "Alembic migration completed successfully."
                    """

                    // Flag that migration ran — used in post{failure} to decide
                    // whether a DB restore is necessary during rollback.
                    env.MIGRATION_RAN = 'true'
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Deploy Backend
        // Purpose: Start the new backend container and wait for it to report
        //          healthy via Docker's built-in health check mechanism.
        //          Docker runs --health-cmd on its own schedule; we just poll the result.
        // ─────────────────────────────────────────────────────────────────────
        stage('Deploy Backend') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        docker run -d \\
                            --name ${BACKEND_CONTAINER} \\
                            --network ${APP_NETWORK} \\
                            --restart unless-stopped \\
                            --env-file ${DEPLOY_DIR}/base/sens.env \\
                            -e DEBUG=False \\
                            -e ENABLE_AUTH=${ENABLE_AUTH} \\
                            -e CORS_ORIGINS=https://iot.polipol-service.pl${APP_PATH},https://iot.polipol-service.pl \\
                            -v ${DEPLOY_DIR}/logs:/app/logs \\
                            --health-cmd="curl -f http://localhost:8000/api/health || exit 1" \\
                            --health-interval=30s \\
                            --health-timeout=10s \\
                            --health-retries=3 \\
                            ${BACKEND_IMAGE}:${params.IMAGE_TAG_BACKEND}
                    """

                    // Poll Docker's health status every 5 seconds for up to 120 seconds (24 retries).
                    // Possible statuses:
                    //   'starting'  — Docker hasn't run the first health check yet (normal early on)
                    //   'healthy'   — health-cmd exited 0
                    //   'unhealthy' — health-cmd failed health-retries times in a row
                    echo "Waiting for backend to become healthy..."
                    def maxRetries = 24
                    for (int i = 1; i <= maxRetries; i++) {
                        def healthStatus = sshCommand(
                            remote: REMOTE,
                            command: "docker inspect --format='{{.State.Health.Status}}' ${BACKEND_CONTAINER}"
                        ).trim()

                        if (healthStatus == 'healthy') {
                            echo "✓ Backend is healthy"
                            break
                        }

                        echo "[${i}/${maxRetries}] Backend status: '${healthStatus}' — retrying in 5s..."
                        if (i == maxRetries) error("Backend did not become healthy within 120 seconds")
                        sleep(5)
                    }
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Deploy Frontend
        // Purpose: Start the new frontend container and wait for it to become healthy.
        //          Backend must be healthy first (previous stage) so Docker DNS can resolve the backend container hostname immediately on frontend start.
        //          --health-start-period gives the frontend grace time before Docker starts counting retries — important for Vite/nginx startup delay.
        // ─────────────────────────────────────────────────────────────────────
        stage('Deploy Frontend') {
            steps {
                script {
                    // Deploy frontend - no port mapping, accessed via nginx
                    // BACKEND_HOSTNAME: use custom param if provided, otherwise fall back to container name
                    def backendHost = params.BACKEND_HOSTNAME?.trim() ? params.BACKEND_HOSTNAME : BACKEND_CONTAINER
                    // define VITE_BASE_PATH based on BASE_PATH env var an APP_PATH
                    def viteBasePath = env.BASE_PATH + APP_PATH
                    sshCommand remote: REMOTE, command: """
                        docker run -d \\
                            --name ${FRONTEND_CONTAINER} \\
                            --network ${APP_NETWORK} \\
                            --restart unless-stopped \\
                            --env-file ${DEPLOY_DIR}/base/sens.env \\
                            -e BACKEND_HOST=${backendHost} \\
                            -e VITE_BASE_PATH=${viteBasePath} \\
                            -e BACKEND_PORT=${BACKEND_PORT} \\
                            -e DNS_RESOLVER=${params.DNS_RESOLVER} \\
                            --health-cmd="wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1" \\
                            --health-interval=30s \\
                            --health-timeout=10s \\
                            --health-start-period=30s \\
                            --health-retries=3 \\
                            ${FRONTEND_IMAGE}:${params.IMAGE_TAG_FRONTEND}
                    """

                    // Wait for frontend health check
                    echo "Waiting for frontend to be healthy..."
                    def maxRetries = 12
                    for (int i = 1; i <= maxRetries; i++) {
                        try {
                            def healthStatus = sshCommand(
                                remote: REMOTE,
                                command: "docker inspect --format='{{.State.Health.Status}}' ${FRONTEND_CONTAINER}"
                            ).trim()

                            if (healthStatus == 'healthy') {
                                echo "✓ Frontend is healthy"
                                break
                            }

                            if (i == maxRetries) {
                                error "Frontend did not become healthy within 60 seconds"
                            }

                            sleep(5)
                        } catch (Exception e) {
                            if (i == maxRetries) throw e
                            sleep(5)
                        }
                    }
                }
            }
        }

        // ─────────────────────────────────────────────────────────────────────
        // STAGE: Cleanup
        // Purpose: Only reached if ALL health checks passed successfully.
        //          Permanently removes the *-previous containers (no longer needed)
        //          and prunes images older than 7 days.
        //          Note: *-previous containers are already stopped — no docker stop needed.
        //          The 'until=168h' filter prevents pruning the image we just deployed.
        // ─────────────────────────────────────────────────────────────────────
        stage('Cleanup') {
            steps {
                script {
                    sshCommand remote: REMOTE, command: """
                        echo "Removing previous containers..."
                        docker rm ${BACKEND_CONTAINER}-previous  || true
                        docker rm ${FRONTEND_CONTAINER}-previous || true

                        echo "Pruning images unused for more than 7 days..."
                        docker image prune -a --filter "until=168h" -f

                        # Remove the schema backup — deployment succeeded, no restore needed.
                        # Comment out for audit purposes.
                        # rm -f ${env.DB_BACKUP_FILE} && echo "Backup file removed: ${env.DB_BACKUP_FILE}"
                    """
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // POST BLOCK
    // Runs AFTER all stages complete, regardless of outcome.
    // Jenkins skips remaining stages on failure and jumps directly here.
    // 'failure' block handles rollback; 'success' just logs completion.
    // ─────────────────────────────────────────────────────────────────────────
    post {

        failure {
            script {
                echo "═══════════════════════════════════════════"
                echo "  Deployment FAILED — initiating rollback"
                echo "═══════════════════════════════════════════"

                // ── Step 1: Stop and remove the failed new containers ─────────
                // '|| true' prevents the rollback itself from failing if
                // a container was never created (e.g. failure happened early).
                sshCommand remote: REMOTE, command: """
                    echo "Stopping and removing failed new containers..."
                    docker stop ${FRONTEND_CONTAINER} || true
                    docker stop ${BACKEND_CONTAINER}  || true
                    docker rm   ${FRONTEND_CONTAINER} || true
                    docker rm   ${BACKEND_CONTAINER}  || true
                """

                // ── Step 2: Restore DB schema if migration ran ────────────────
                // Only restore if alembic upgrade head actually ran — if failure
                // happened before the migration stage, the schema is untouched.
                if (env.MIGRATION_RAN == 'true' && env.DB_BACKUP_FILE) {
                    echo "Migration was applied — restoring schema from backup: ${env.DB_BACKUP_FILE}"
                    sshCommand remote: REMOTE, command: """
                        # Restore the schema backup taken before migration using dump_restore_db.sh.
                        # '--clean' drops existing objects before restoring so the schema reverts cleanly.
                        # '--no-confirm' skips interactive prompt (required for CI/CD).
                        # Source and target are both the same Postgres container (in-place restore).
                        ~/backups/dump_restore_db.sh \\
                            --action        restore \\
                            --mode         schema \\
                            --target-container ${POSTGRES_CONTAINER} \\
                            --target-user    ${POSTGRES_USER} \\
                            --target-db      ${POSTGRES_DB} \\
                            --container-backup-dir ${CONTAINER_BACKUP_DIR} \\
                            --clean \\
                            --no-confirm

                        # Run VACUUM ANALYZE after restore to update planner statistics.
                        # This is recommended by dump_restore_db.sh itself after a restore.
                        docker exec ${POSTGRES_CONTAINER} vacuumdb \\
                            -U ${POSTGRES_USER} \\
                            -d ${POSTGRES_DB} \\
                            --analyze

                        echo "Database schema restored to pre-migration state."
                    """
                } else {
                    echo "Migration did not run — no DB restore needed."
                }

                // ── Step 3: Rename *-previous back to original names ──────────
                // 'docker inspect' checks existence before renaming to avoid errors
                // if failure happened before the Stop & Rename stage ran.
                sshCommand remote: REMOTE, command: """
                    echo "Renaming *-previous containers back to original names..."
                    docker inspect ${BACKEND_CONTAINER}-previous  >/dev/null 2>&1 && \\
                        docker rename ${BACKEND_CONTAINER}-previous  ${BACKEND_CONTAINER}  || true
                    docker inspect ${FRONTEND_CONTAINER}-previous >/dev/null 2>&1 && \\
                        docker rename ${FRONTEND_CONTAINER}-previous ${FRONTEND_CONTAINER} || true
                """

                // ── Step 4: Restart original containers ───────────────────────
                // 'docker start' reuses the EXACT original 'docker run' configuration:
                // all volumes, environment variables, network settings, restart policies,
                // and health check settings are preserved from the original run command.
                // Start order: backend first, then frontend (frontend needs backend DNS).
                sshCommand remote: REMOTE, command: """
                    echo "Restarting original containers..."
                    docker start ${BACKEND_CONTAINER}  || true
                    docker start ${FRONTEND_CONTAINER} || true
                    echo "Rollback complete — original containers are running again."
                """
            }
        }

        success {
            echo "✓ Deployment of ${params.TARGET_SERVER} completed successfully."
        }
    }
}
