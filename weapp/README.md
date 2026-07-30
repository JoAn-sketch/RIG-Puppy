# Puppy WeChat Mini Program MVP

This mini program is a minimal MVP for collecting child profile information
through a multi-step questionnaire and submitting the age field to the Puppy backend.

## What is included

- multi-step profile form
- nickname input
- age picker: `3-11`
- favorite things: choose 3
- favorite dog type
- preferred interaction
- parent help expectations
- fixed device ID submission
- simple validation
- `wx.login -> code -> 后端换 openid`

## Files you will likely edit first

- `utils/config.js`
  - replace `API_BASE_URL` with your real backend address
- `project.config.json`
  - replace `appid` with your real WeChat Mini Program AppID

## Current local debug API

The mini program calls:

`POST {API_BASE_URL}/wechat-mini/login`

and then:

`POST {API_BASE_URL}/child-profile`

Current default:

`http://127.0.0.1:8002/xiaozhi/api/v1`

Current login payload:

```json
{
  "code": "wx_login_code"
}
```

Current backend profile payload:

```json
{
  "openid": "wx_openid_xxx",
  "deviceId": "E8:3D:C1:F5:49:B8",
  "age": 6
}
```

Other child profile fields are currently stored locally in mini program storage
and displayed on the `我的档案` page.

## How to run

1. Open WeChat DevTools
2. Import this folder:
   - `/Users/joan/Desktop/puppy/weapp`
3. Fill your real `appid`
4. In local debug, make sure request domain restriction will not block localhost
5. Compile

## WeChat DevTools local debug note

If requests to `127.0.0.1` fail in DevTools, check:

1. `详情 -> 本地设置`
2. enable the option similar to:
   - `不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书`

This is only for local development.

## Notes

- This version uses a fixed `deviceId`
- Backend `wechat.mini.appid` and `wechat.mini.secret` must be configured before login works
