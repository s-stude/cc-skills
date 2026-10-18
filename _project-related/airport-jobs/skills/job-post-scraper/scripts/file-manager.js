const fs                   = require( 'fs' );
const path                 = require( 'path' );
const { generateFilename } = require( './utils' );
const { loadConfig }       = require( './config' );

/**
 * Saves a job post to the configured directory
 * @param {Object} jobData - The job post data with meta.uid
 * @returns {Object} {filename, uid}
 */
function saveJobPost( jobData ) {
    const cfg      = loadConfig();
    const uid      = jobData.meta.uid;
    const filename = generateFilename( uid );
    const filePath = path.join( cfg.jobPostsDir, filename );

    // Ensure directory exists
    if (!fs.existsSync( cfg.jobPostsDir )) {
        fs.mkdirSync( cfg.jobPostsDir, { recursive: true } );
    }

    fs.writeFileSync( filePath, JSON.stringify( jobData, null, 2 ), 'utf8' );

    return { filename, uid };
}

module.exports = {
    saveJobPost
};
