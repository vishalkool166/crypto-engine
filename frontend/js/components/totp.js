const TOTP = {
    async prompt(title, subtitle) {
        return new Promise((resolve) => {
            const app = window._app
            if (!app) {
                resolve(null)
                return
            }
            app.requireTotp(title, subtitle).then(code => {
                resolve(code)
            })
        })
    },

    async confirm(title, subtitle, action) {
        const app = window._app
        if (!app) return { success: false, reason: 'App not initialized' }

        const code = await this.prompt(title, subtitle)
        if (!code) return { success: false, reason: 'Cancelled' }

        try {
            const result = await action(code)
            if (result && !result.success) {
                app.totp.error = result.reason || 'Invalid TOTP code'
                app.totp.show  = true
                app.totp.code  = ''
                return { success: false, reason: result.reason }
            }
            return { success: true, data: result }
        } catch (e) {
            return { success: false, reason: e.message || 'Action failed' }
        }
    },

    showError(msg) {
        const app = window._app
        if (!app) return
        app.totp.error = msg
        app.totp.show  = true
        app.totp.code  = ''
    },

    close() {
        const app = window._app
        if (!app) return
        app.totp.show  = false
        app.totp.code  = ''
        app.totp.error = ''
    },
}

window.TOTP = TOTP