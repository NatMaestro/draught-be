from django.db import migrations


def forward(apps, schema_editor):
    FaqItem = apps.get_model("cms", "FaqItem")
    BlogPost = apps.get_model("cms", "BlogPost")

    FaqItem.objects.filter(question="How do installs work on phones?").update(
        answer=(
            "On Android (Chrome and most Chromium browsers) you get a native-style Install sheet "
            "when conditions are met—same install flow browsers use for other PWAs. Apple’s Safari "
            "doesn’t expose that sheet for websites; staying in the browser or a future App Store "
            "build are the options there."
        )
    )

    new_body = (
        "Draught is built as a PWA — the same packaging model many games use outside the big "
        "app stores. On Android phones with Chromium-based browsers that support installs, Chrome will "
        "surface an Install or Add-to launcher flow backed by manifest + offline shell. That behaves "
        "like grabbing an app listing: confirmation dialog, launcher icon, and the app separated from "
        "tabs.\n\n"
        "Exactly when the banner or menu entry appears is up to Chrome’s installability signals "
        "(HTTPS, icons, manifest, service worker lifecycle). Keeping the stable game URL pinned in "
        "bookmarks is OK while you wait; the install UX is additive once the browser is happy.\n\n"
        "On iPhones, Safari historically does not offer that same programmatic install banner for "
        "arbitrary sites—we don’t bury you in workaround steps anymore. Playing in Safari works; a "
        "future native build would be where iOS gets parity with Chrome’s install sheet.\n\n"
        "Bottom line for players: Android users should expect a familiar Install flow once they open "
        "the hosted game on Chrome. Everyone else taps through to play in-browser until we publish "
        "store packages if demand says we should."
    )

    BlogPost.objects.filter(slug="install-on-your-phone").update(
        title="Installing Draught on Android (PWAs Chrome gives you)",
        excerpt=(
            "Where Chrome exposes a proper Install sheet and what that means versus loading "
            "the site in Safari on iPhones."
        ),
        body=new_body,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0002_seed_cms_content"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
