'use strict';

const utils = require('./utils');

/**
 * Default configuration options
 *
 * @readonly
 * @type {object}
 */
const defaultConfig = {
    /**
     * Core configuration options
     *
     * @type {object}
     */
    core: {
        /**
         * Forum Provider
         *
         */
        provider: process.env.PROVIDER || 'nodebb',
        /**
         * Username the bot will log in as
         *
         * @default
         * @type {string}
         */
        username: process.env.BOT_USERNAME || 'default_username',
        /**
         * Password the bot will log in with
         *
         * @default
         * @type {string}
         */
        password: process.env.BOT_PASSWORD || 'default_password',
        /**
         * User the bot will consider owner
         *
         * Owner promotes the user to virtual trust level 9 (above forum admins)
         *
         * @default
         * @type {string}
         */
        owner: process.env.BOT_OWNER || 'default_owner',
        /**
         * Base URL for the discourse instance to log into
         *
         * Is case sensitive
         *
         * @default
         * @type {string}
         */
        forum: process.env.FORUM_URL || 'https://what.thedailywtf.com'
    },
    /**
     * Plugin configuration.
     *
     * See `Plugin Configuration` for details
     *
     * @type {object}
     */
    plugins: {}
};

if (process.env.PLUGINS) {
    const plugins = process.env.PLUGINS.split(',');
    for (const plugin of plugins) {
        defaultConfig.plugins[plugin.trim()] = true;
    }
}

module.exports = defaultConfig;
