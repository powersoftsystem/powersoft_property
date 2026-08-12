### Powersoft Property

Property management for ERPNext

### Install

Two commands. Same as any other ERPNext app.

```bash
cd ~/frappe-bench
bench get-app https://github.com/powersoftsystem/powersoft_property.git
bench --site your.site install-app powersoft_property
```

That is the whole install. There is no third step.

Everything the app needs it does itself:

- **Fixtures** import during `install-app`. No separate migrate.
- **Income accounts** (`Rental Income`, `Service Charge Income`) are created
  under your company's own Income group, with the root type checked, and wired
  into any rent or service charge item found.
- **Dashboard cards** scope themselves to your company. They cannot carry a
  company filter as a fixture, so the app writes it in at run time - on the
  next migrate, when a company is created, when a property is added or
  removed, and on login as a backstop. If you install the app before creating
  your company, the cards pick it up the moment you do.

One thing is left to you on purpose: **create your own asset categories.** The
app creates none. Some businesses buy land and build; others buy a finished
building and let it straight away. Create whatever fits how you work and map
their accounts.

### If something looks wrong

| Symptom | Cause |
|---|---|
| Cards read across all companies | Log out and back in, or run `bench --site your.site migrate`. Both re-scope. |
| Assets appear unstyled / logo missing | `bench build` did not run. On a bench where the bench user's Node comes from nvm, use `sudo -iu <bench-user> bench build` - a login shell. `sudo -u` picks up the system Node, and Frappe v16 needs Node 24+. |
| Rent posts to the wrong account | Check the income account on your rent item, and that its root type is Income. |

