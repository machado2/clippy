'use strict';
/**
 * @module clippy
 */

const utils = require('../lib/utils');
const debug = require('debug')('sockbot:plugins:summoner');
const { Configuration, OpenAIApi } = require("openai");

const openai = new OpenAIApi(new Configuration({ apiKey: process.env.OPENAI_KEY }));

async function moderateContent(content) {
    const response = await openai.createModeration({ input: content });
    const moderation_result = response.data.results[0].flagged;
    if (moderation_result) {
        debug(`Content flagged: ${content}`);
    }
    return !moderation_result;
}

async function generateContent(context, postContent, userName) {
    const prompt = `
You are Clippy, a parody of the Microsoft Office Assistant. Your answers should be funny and entertaining.
Your answers will attempt to be funny, helpful and correct. If it's out of your depth, you'll try to be just
funny and not necessarily correct. But you'll pretend to be correct and confident anyway.

You're talking in a forum, and your answers should follow the markdown format, without any links or images.
Your answers can be long if the post you are replying warrants it. 
All usernames are prefixed with an '@' character.

You are talking to a user named @${userName}.

These are the latest posts in the topic:

${context}

This is the content of the post you're replying:

${postContent}

Clippy says:

`;

    if (!(await moderateContent(prompt))) {
        return null;
    }

    const response = await openai.createChatCompletion({
        model: "gpt-3.5-turbo",
        messages: [{ role: "user", content: prompt }],
    });

    const content = response.data.choices[0].message?.content;
    return content;
}


/**
 * Plugin generation function.
 *
 * Returns a plugin object bound to the provided forum provider
 *
 * @param {Provider} forum Active forum Provider
 * @param {object|Array} config Plugin configuration
 * @returns {Plugin} An instance of the Summoner plugin
 */
module.exports = function clippy(forum, config) {

    /**
     * Handle a mention notification.
     *
     * Choose a random message and reply with it
     *
     * @param {Notification} notification Notification event to handle
     * @returns {Promise} Resolves when event is processed
     */
    async function handler(notification) {
        debug('clippy received a mention notification!');
        try {
            const user = await notification.getUser();
            debug(`clippy responding to ${user.username}`);
    
            const thepost = await forum.Post.get(notification.postId);
            const topic = await forum.Topic.get(notification.topicId);
            let contextPosts = [];
            await topic.getLatestPosts(async (p) => {
                const postAuthor = await forum.User.get(p.authorId);
                contextPosts.push({content: p.content, author: postAuthor.username});
            });
    
            contextPosts = contextPosts.slice(-100);
            while (contextPosts.length > 1 && contextPosts.map((p) => p.content).join('\n\n').length > 8000) {
                contextPosts.shift();
            }
            const textLatestPosts = contextPosts.map((p) => `${p.author}: ${p.content}`).join('\n\n');
            const response = await generateContent(textLatestPosts, thepost.content, user.username);
            if (!response) {
                return;
            }
    
            return forum.Post.reply(notification.topicId, notification.postId, response);
        } catch (err) {
            forum.emit('error', err);
            return Promise.reject(err);
        };
    }
    

    /**
     * Activate the plugin
     */
    function activate() {
        forum.on('notification:mention', handler);
    }

    /**
     * Deactivate the plugin
     */
    function deactivate() {
        forum.off('notification:mention', handler);
    }

    return {
        activate: activate,
        deactivate: deactivate,
        handler: handler
    };
};

