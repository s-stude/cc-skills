#!/usr/bin/env node

const crypto = require( 'crypto' );

const generateShortUID = ( prefix ) => {
    const randomBytes = crypto.randomBytes( 6 );
    const shortUID    = randomBytes.toString( 'base64' )
        .replace( /\+/g, '' )
        .replace( /\//g, '' )
        .replace( /=/g, '' )
        .substring( 0, 8 );

    if (prefix) return `${ prefix }_${ shortUID }`.toLowerCase();

    return `${ shortUID }`.toLowerCase();
};

module.exports = { generateShortUID }