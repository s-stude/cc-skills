const fs   = require( 'fs' );
const path = require( 'path' );

/**
 * Finds the project root directory by looking for markers
 * Priority: package.json, .git directory, or back directory
 */
function findProjectRoot() {
    let currentDir = __dirname;

    while (currentDir !== '/') {
        // Check for package.json
        if (fs.existsSync( path.join( currentDir, 'package.json' ) )) {
            return currentDir;
        }

        // Check for .git directory
        if (fs.existsSync( path.join( currentDir, '.git' ) )) {
            return currentDir;
        }

        // Check for back directory (fallback for legacy detection)
        if (fs.existsSync( path.join( currentDir, 'back' ) )) {
            return currentDir;
        }

        currentDir = path.dirname( currentDir );
    }

    // Fallback to current working directory
    return process.cwd();
}

/**
 * Loads configuration from multiple sources with priority:
 * 1. Environment variables (highest priority)
 * 2. Config file (.job-processor.config.json)
 * 3. Default paths (lowest priority)
 *
 * @returns {Object} Configuration object
 */
function loadConfig() {
    const projectRoot = findProjectRoot();

    // Default configuration - simplified for single-URL processing
    const defaults = {
        jobPostsDir: 'back/data/job-posts',
        orgsDir    : 'back/data/orgs',
    };

    // Try to load config file
    const configPath = path.join( projectRoot, '.job-processor.config.json' );
    let fileConfig   = {};

    if (fs.existsSync( configPath )) {
        try {
            const content    = fs.readFileSync( configPath, 'utf8' );
            const fullConfig = JSON.parse( content );
            // Only extract the fields we need
            fileConfig       = {
                jobPostsDir: fullConfig.jobPostsDir,
                orgsDir    : fullConfig.orgsDir,
            };
        } catch (err) {
            console.warn( `Warning: Failed to parse config file at ${ configPath }:`, err.message );
        }
    }

    // Environment variable overrides
    const envConfig = {};
    if (process.env.JOB_POSTS_DIR) {
        envConfig.jobPostsDir = process.env.JOB_POSTS_DIR;
    }
    if (process.env.ORGS_DIR) {
        envConfig.orgsDir = process.env.ORGS_DIR;
    }

    // Merge configurations (env > file > defaults)
    const config = {
        ...defaults,
        ...fileConfig,
        ...envConfig
    };

    // Convert relative paths to absolute paths
    const absoluteConfig = {
        jobPostsDir: path.isAbsolute( config.jobPostsDir )
            ? config.jobPostsDir
            : path.join( projectRoot, config.jobPostsDir ),
        orgsDir    : path.isAbsolute( config.orgsDir )
            ? config.orgsDir
            : path.join( projectRoot, config.orgsDir ),
    };

    return absoluteConfig;
}

module.exports = {
    findProjectRoot,
    loadConfig
};
