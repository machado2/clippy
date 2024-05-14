'use strict';
/**
 * @module clippy
 */

const utils = require('../lib/utils');
const debug = require('debug')('sockbot:plugins:summoner');
const { NodeHtmlMarkdown } = require('node-html-markdown');
const fs = require('fs');
const path = require('path');

async function moderateContent(content) {
    const response = await openai.createModeration({ input: content });
    const moderation_result = response.data.results[0].flagged;
    if (moderation_result) {
        debug(`Content flagged: ${content}`);
    }
    return !moderation_result;
}

// system_message is initialized with the contents of the file ../system_message.txt

const sysmsgpath = path.join(__dirname, 'system_message.txt');

let system_message = fs.readFileSync(sysmsgpath, 'utf8');

const system_message_complement = `
You're talking in a forum, and your answers should follow the markdown format, without any links or images.
All usernames are prefixed with an '@' character.

Your username in the forum is 'clippy'.`;

function format_system_message() {
    return {
        role: "system",
        content: system_message + '\n' + system_message_complement
    };
}

async function generateContent(messages) {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${process.env.OPENROUTER_API_KEY}`,
            "X-Title": `Clippy`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            model: "meta-llama/llama-3-70b-instruct",
            // model: "openai/gpt-3.5-turbo",
            // model: "mistralai/mixtral-8x22b",
            temperature: 1,
            messages,
        })
    });
    const textData = await response.text();
    console.log(textData);
    const jsonData = JSON.parse(textData);
    // const jsonData = await response.json();
    console.log(JSON.stringify(jsonData));
    const content = jsonData.choices[0].message?.content;

    // remove any trailing text in the format of <|xyz|>
    if (content) {
        return content.replace(/<\|.*\|>$/, '');
    }

    return content;
}

function convertHtmlToMarkdown(htmlString) {
    // Create an instance of NodeHtmlMarkdown
    const nhm = new NodeHtmlMarkdown();

    // Convert the HTML string to Markdown
    const markdown = nhm.translate(htmlString);

    return markdown;
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
                contextPosts.push({ content: p.content, author: postAuthor.username });
            });

            contextPosts = contextPosts.slice(-100);
            // while (contextPosts.length > 1 && contextPosts.map((p) => p.content).join('\n\n').length > 8000) {
            // contextPosts.shift();
            //}
            let messages = [format_system_message()];
            for (const p of contextPosts) {
                // name must be ^[a-zA-Z0-9_-]{1,64}$
                let sanitizedName = p.author.replace(/[^a-zA-Z0-9_-]/g, '').substring(0, 64);
                if (sanitizedName.length == 0) {
                    sanitizedName = 'user';
                }
                let role = sanitizedName.toLowerCase().trim() == 'clippy' ? 'assistant' : 'user';
                messages.push({
                    role,
                    name: sanitizedName,
                    content: convertHtmlToMarkdown(p.content)
                });

                // the command !clearcontext clear the context of the conversation
                if (p.content.includes("!clearcontext")) {
                    messages = [format_system_message()];
                }

                // the command !system_message(<new message>) changes the system message
                const system_message_regex = /!system_message ?\((.*)\)/;
                const match = p.content.match(system_message_regex);
                if (match) {
                    system_message = match[1];
                    fs.writeFileSync(sysmsgpath, system_message);
                    messages = [format_system_message()];
                }

            }
            const response = await generateContent(messages);
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
