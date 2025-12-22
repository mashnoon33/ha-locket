# Home Assistant Locket Integration

A Home Assistant custom integration to display your Locket moments as a camera widget.

## Features

- Display your latest Locket moment as a camera entity
- Automatic token refresh
- Shows missed moments count and moment metadata
- Phone OTP authentication via Home Assistant configuration UI

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL: `https://github.com/mashnoon33/ha-locket`
5. Select category: **Integration**
6. Click "Add"
7. Search for "Locket" and install
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/locket` folder to your Home Assistant `custom_components` directory:
   ```
   <config>/custom_components/locket/
   ```

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Add Integration

4. Search for "Locket" and follow the setup wizard

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Locket"
4. Enter your phone number in E.164 format (e.g., +1234567890)
5. Enter the verification code sent to your phone
6. The integration will authenticate and create the camera entity

## Usage

After configuration, you'll have a camera entity called `camera.locket_moment` that displays your latest Locket moment.

You can add it to your dashboard using a picture-glance or picture-entity card:

```yaml
type: picture-entity
entity: camera.locket_moment
show_name: true
show_state: true
```

Or use it in a Lovelace card:

```yaml
type: picture-glance
entities:
  - entity: camera.locket_moment
    name: Latest Moment
```

## Entity Attributes

The camera entity includes the following attributes:
- `missed_moments`: Number of missed moments
- `caption`: Caption of the current moment (if available)
- `canonical_uid`: Unique ID of the moment
- `user`: User ID of the moment creator
- `moment_date`: ISO timestamp of when the moment was created

## Troubleshooting

- If the camera shows "unavailable", check your credentials in the integration settings
- The integration automatically refreshes tokens when they expire
- Check the Home Assistant logs for any error messages

## Notes

- The integration polls for new moments every 60 seconds by default
- Your credentials are stored securely in Home Assistant's configuration
- This integration is not officially supported by Locket

