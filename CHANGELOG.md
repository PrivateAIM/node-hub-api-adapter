# Changelog

## [0.3.5](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.3.4...v0.3.5) (2026-01-20)


### Features

* **events:** add event logging to autostart analyses ([bed1852](https://github.com/PrivateAIM/node-hub-api-adapter/commit/bed1852e382a3ffae8eb1b3b7d5f0bdb1b2f839f))
* **events:** add event retrieval endpoint ([dd86975](https://github.com/PrivateAIM/node-hub-api-adapter/commit/dd86975248df509d1235d1047c1cc77d29ea3e13))
* **events:** add middleware for logging events ([c04f86b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c04f86b9da4f0400a8c76e0907f422110e2fb68b))
* **events:** combine event methods into class for middleware and decorator usage ([20f96bb](https://github.com/PrivateAIM/node-hub-api-adapter/commit/20f96bb28a5e2eb02aad45ccf46da6a41ae16d6e))

## [0.3.4](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.3.3...v0.3.4) (2025-12-17)


### Features

* **auth:** add claim name variable so parsing is idp agnostic ([567e8ec](https://github.com/PrivateAIM/node-hub-api-adapter/commit/567e8ecd583766b738dba888ff1ed10ac1344874))
* **auth:** create steward role dependency ([645ec80](https://github.com/PrivateAIM/node-hub-api-adapter/commit/645ec8085502c7dc5ba7fbb8a728591019e344af))
* **auth:** integrate RBAC into relevant endpoints ([f3045db](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f3045db07de0271c4109b06d2b2d2f42b68cd7aa))


### Documentation

* update docs with new env var and detailed RBAC and autostart sections ([17c6652](https://github.com/PrivateAIM/node-hub-api-adapter/commit/17c6652ab958b21e773634bef22b36eb24f50fee))

## [0.3.3](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.3.2...v0.3.3) (2025-11-21)


### Bug Fixes

* **hub:** add pydantic type error catch ([7abed9c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7abed9ce599a182ade70ef7424eb9e70c131e421))

## [0.3.2](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.3.1...v0.3.2) (2025-11-12)


### Bug Fixes

* **results:** add query params to delete ep ([45f1252](https://github.com/PrivateAIM/node-hub-api-adapter/commit/45f1252a5df984d3668af2374c11b3ede78e20b9))

## [0.3.1](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.3.0...v0.3.1) (2025-11-11)


### Features

* **po:** parse new status response ([a5cb06c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a5cb06c88e7dcb78eaf9498ac43008c3cb223747))
* **results:** add results endpoint for local file deletion ([fa8a87b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/fa8a87b9d5fec1ec2378368df801d60d24f800d2))


### Bug Fixes

* **po:** catch multiple OK status codes during pod start ([18eb410](https://github.com/PrivateAIM/node-hub-api-adapter/commit/18eb410cabd7c61a31dfd9c8abe1e3f693510177))
* remove obsolete param from list_projects ([93bb994](https://github.com/PrivateAIM/node-hub-api-adapter/commit/93bb994935b6e338b193085a630061fa0b85d75c))
* **results:** change Path to Query for project_id ([ff5c8d9](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ff5c8d934ee2965d8a3cdec2a023b49f0ebf91bc))


### Reverts

* **po:** add zombies option back to PO cleanup ([7f21aed](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7f21aed9d1288e7453bba9af2d126c8fe215c95c))


### Documentation

* **error:** improve error messages for proxy-related issues ([2566012](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2566012636bbca1242ffd4493e0ff739616bb587))
* **error:** improve error messages for proxy-related issues ([44f5693](https://github.com/PrivateAIM/node-hub-api-adapter/commit/44f56931135f70ad2d3bb4e66ba8a0da4f1a7217))

## [0.3.0](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.14...v0.3.0) (2025-10-22)


### ⚠ BREAKING CHANGES

* force breaking change update

### Features

* force breaking change update ([ec24b89](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ec24b8970276b763cfbdb37164c73cd90e23bcb7))
* **meta:** add analysis terminate method to meta router ([7060f2a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7060f2a2657d712f430d61f8ae37af85d1be894f))
* **po:** update PO endpoints and response models ([b447242](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b44724267f299938652bb0c7af62c19f661b43f6))


### Bug Fixes

* **po:** parsing pod status response ([f185a0e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f185a0e7720cb1b579587dcc355761f443582bfb))

## [0.2.14](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.13...v0.2.14) (2025-10-14)


### Features

* **error:** add ReadTimeout error when querying hub ([d41ef9a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d41ef9a9017c235067b9299815e5ef7e9ceeeb55))

## [0.2.13](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.12...v0.2.13) (2025-10-02)


### Bug Fixes

* **headless:** add HTTPStatusError catch ([682a496](https://github.com/PrivateAIM/node-hub-api-adapter/commit/682a49690db473f941e9f90416ada7f1a0b21c72))
* **headless:** catch more PO errors and limit analyses scope to 1 day ([eb4a3b5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/eb4a3b5b2d189da851554f36cd5bed1bc6794661))
* **headless:** disable kong route check if aggregator node ([4c2f336](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4c2f336bb2eab097954c958639334ed1822d5e4a))
* **meta:** allow analysis to be restarted ([62fc29a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/62fc29ae5ac5680e13fd922273910126fe7376ea))

## [0.2.12](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.11...v0.2.12) (2025-09-24)


### Features

* **kong:** add specific services to error messages ([6009c3a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6009c3a4153f34d1a08a35fd5c70073fe4c5fc13))
* **kong:** first version connection test endpoint ([52954f2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/52954f2edbe3a65f236f0956bad393a35750ba85))
* **kong:** incorporate connection test during data store initialization ([050f117](https://github.com/PrivateAIM/node-hub-api-adapter/commit/050f117559d0f3bff54499d6ffbff9b4a34778aa))
* **meta:** add endpoint for initializing an analysis using headless methods ([2ac9818](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2ac981879d4af1555638e9ef2bd2bc442ab5c14e))


### Bug Fixes

* **auth:** raise HTTPException on invalid robot UUID ([726bb6f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/726bb6fef6cead77fb105cd4da2b59b371bf5653))
* **headless:** update exceptions ([976092a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/976092a0518f3c306e1c1680ee6a7b63252ceae2))
* **kong:** better enum handling ([fc4cd33](https://github.com/PrivateAIM/node-hub-api-adapter/commit/fc4cd33851f11253777e481d2e39486d518b7af7))


### Documentation

* add KONG_PROXY_SERVICE_URL to README ([8a4482b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8a4482b624957ae5c43306d2cc96e7a59863bc36))

## [0.2.11](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.10...v0.2.11) (2025-09-05)


### Features

* **headless:** add ability to define probe interval via env var ([c497096](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c497096d81b6138b81c00a177e3817cbd7e130a7))
* **headless:** add env var to toggle headless ([1fd690f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1fd690f8865ce62d9a236b376fdccea211ca956c))
* **ssl:** add ability to provide additional certificates ([764026e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/764026e50a3a93dc21e791b5f994ada1d9b0881b))


### Bug Fixes

* **headless:** working analysis start and improved try/except ([79c7970](https://github.com/PrivateAIM/node-hub-api-adapter/commit/79c7970a009cb8be832b5f4fe8d1709a6c5a5dd2))
* **kong:** add missing dependency injection ([0ac11ef](https://github.com/PrivateAIM/node-hub-api-adapter/commit/0ac11ef236ead454e6987a5cf4fc3bfd6efab676))


### Documentation

* **logs:** fixed a mistake in the logs ([8992b8f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8992b8f2139f384992e44af18d81365292514cfc))
* **ssl:** add EXTRA_CA_CERTS env var to README ([386e815](https://github.com/PrivateAIM/node-hub-api-adapter/commit/386e81504ef5a3200340c6c2a47a668a18d8c935))

## [0.2.10](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.9...v0.2.10) (2025-08-25)


### Features

* **hub:** add endpoint for getting nodes and node type ([5d65c24](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5d65c2473a537461e87940a8f70a91daf4d75c05))
* **hub:** add endpoint for getting nodes and node type ([2fe7b6b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2fe7b6b9591a529a9b0980091bb2dd3708bdec28))
* **po:** implement cleanup ep ([ccc7119](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ccc7119a6738c0278c7895798564cefd72e72a45))


### Documentation

* **hub:** fix path param description ([ef2b471](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ef2b471aad6955c5e4d7a0b011c09d0d28b1ae6e))

## [0.2.9](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.8...v0.2.9) (2025-08-07)


### Features

* **proxy:** respect env vars for proxies including NO_PROXY ([5cfd6d5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5cfd6d52010cc2e9310ae1ae0fd8f4b498b40f41))
* **proxy:** respect env vars for proxies including NO_PROXY ([08bc017](https://github.com/PrivateAIM/node-hub-api-adapter/commit/08bc0177697f7746107d98ba5af8497cea408fe9))


### Bug Fixes

* **proxy:** change env var for proxy idp check ([d86b203](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d86b2038f22c104b1f11a79412efb0431c94598e))


### Documentation

* **proxy:** add note ([84cdf00](https://github.com/PrivateAIM/node-hub-api-adapter/commit/84cdf001ef99f36d51adfed902e102e3e12a8d0f))
* update README with table ([9a36352](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9a36352c4c584e3cbdbf62b03aab7c9ee80b6621))

## [0.2.8](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.7...v0.2.8) (2025-06-26)


### Features

* **proxy:** allow optional proxy bypassing for internal node services authentication ([9451b12](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9451b124ed4bf492f15f42b27c8f7c04a1183626))


### Bug Fixes

* **proxy:** enable proxy mounts for /token endpoint ([8f54e6c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8f54e6cdb9c9c150ab63eec8170dcab14a86b600))

## [0.2.7](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.6...v0.2.7) (2025-06-17)


### Features

* **proxy:** add custom PyJWKClient class to handle IDP token ([7190ae9](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7190ae9a004dee1328e388777842b9811adc7711))
* **proxy:** enable proxies for hub communication ([db7696c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/db7696c318d4b33899514ead052d38f19c89874c))


### Bug Fixes

* **hub:** pass hub URLs to hub client ([11478dc](https://github.com/PrivateAIM/node-hub-api-adapter/commit/11478dc7bd21e0aa3e2323e70616b98dc0f6f925))
* **logs:** improved logging to console and file ([f170d12](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f170d12e4bbb96ec305c1ff73951debc908ba76a))


### Documentation

* add proxy env vars to README ([bd6de95](https://github.com/PrivateAIM/node-hub-api-adapter/commit/bd6de95a9a64637a5f977ea2c9c9f9bc891fdfff))

## [0.2.6](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.5...v0.2.6) (2025-06-04)


### Features

* add hub client to final endpoints ([6a3eb68](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6a3eb68bb47be6a60d4849cde85b5fa6a35ad92e))
* **auth:** add ability to force JWKS ([44f2960](https://github.com/PrivateAIM/node-hub-api-adapter/commit/44f29609a3edab792b1ec104ef7e761647229b6b))
* **auth:** allow lazy loading of config processing ([860a6f2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/860a6f2decb6685b4c7d7cab8fc88ba381d350dc))
* **hub:** enable most query params for project and analysis nodes ([b38488e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b38488eeda79fec8c4abee86dceaf4663d68ac47))
* **hub:** working image URL retrieval using hub client ([84767d5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/84767d52f63feae6e88450b805560b6235cc4705))


### Bug Fixes

* **auth:** proper response when bad issuer URL provided ([9c90b68](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9c90b68ec171d2e343bc33b4eab9fc64318cb985))
* **hub:** enable account id and secret retrieval ([3202d50](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3202d50c46444228154aca1c034cbdb798e4bc99))
* **kong:** properly catch and handle manually raise HTTPExceptions ([0abc5be](https://github.com/PrivateAIM/node-hub-api-adapter/commit/0abc5be8b5c0a4a875a0219dc3d6df755cb4a5a6))


### Performance Improvements

* **idp:** create attempt routine for contacting the IDP ([e4293b2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e4293b2628b37a7372ecb8e9019e68dd5aee1a48))

## [0.2.5](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.4...v0.2.5) (2025-05-16)


### Features

* **idp:** allow for separate user IDP and dynamically build oidc config ([c6f27a3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c6f27a322ddddebfbf73b659f981ae9f12f9d9c4))
* **idp:** allow for separate user IDP and dynamically build oidc config ([63cfaa8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/63cfaa8cee2965c7a9991b25a02a6d44729d9dc6))

## [0.2.4](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.3...v0.2.4) (2025-05-08)


### Bug Fixes

* **kong:** revert to updated version and fix project route path bug ([52eaeb6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/52eaeb6c1373fa3987e90148361b7880eb6c2a34))


### Reverts

* **kong:** remove data store name suffix ([7911846](https://github.com/PrivateAIM/node-hub-api-adapter/commit/79118467b5c8ef6ec5d4ff9a53bda83e83cac51d))


### Documentation

* **kong:** update datastore ep ([b324a71](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b324a715f72852bb1b6cf6910621e9fd597c2ced))

## [0.2.3](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.2...v0.2.3) (2025-05-07)


### Features

* add kong_token to /po ep ([f3ead40](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f3ead40e5405cfc80a68a0e6aa30281cdb9c0d5a))
* add kong_token to /po ep ([96ce4b2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/96ce4b2e70c885601c202e1fdb7f7b2f140fba27))
* improved downstream error analysis ([55af611](https://github.com/PrivateAIM/node-hub-api-adapter/commit/55af611e8848d9f7d035bca62f2b4f234cea53ce))


### Bug Fixes

* po endpoint param data type ([d4712b2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d4712b27e7f006c32360c50e938406b94ff9f9bf))

## [0.2.2](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.1...v0.2.2) (2025-05-06)


### Bug Fixes

* enable data store creation with same name but different type ([1ec3ddf](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1ec3ddf97d79740b27fef0364be7ba41cd028e9a))
* enable data store creation with same name but different type ([c853519](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c85351997663c3ca417e0cbf36fe00472f506d9b))

## [0.2.1](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.2.0...v0.2.1) (2025-05-05)


### Bug Fixes

* allow follow redirects ([1dbcdad](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1dbcdada1d2f950b882e7bfff0341f9588f55f0b))
* remove root path from downstream microsvc endpoint paths ([3accbd1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3accbd11735bfc5be67bcf601628e25251b2d28f))
* remove root path from downstream microsvc endpoint paths ([f53a64d](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f53a64d5757a6a7bcc4f453916955478f94a4105))
* update deps ([93b23bd](https://github.com/PrivateAIM/node-hub-api-adapter/commit/93b23bd4313c6c8409f7e3836ceee2a364db2433))

## [0.2.0](https://github.com/PrivateAIM/node-hub-api-adapter/compare/v0.1.4...v0.2.0) (2025-04-10)


### Features

* add additional request params to route decorator ([956a515](https://github.com/PrivateAIM/node-hub-api-adapter/commit/956a51509c7146d129b16647cfb978167bee6535))
* add analysis and image hub eps with models ([1670fc0](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1670fc0fc91afdd4f2c5468aaa295085bbc03473))
* add CLI ([8ccc723](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8ccc723fe62e17c73ea086589bc8617cc7ced5cc))
* add conditions for handling StreamingResponses ([7c2f47a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7c2f47af81b3044470df92cac609319e5a48b552))
* add methods for merging openapi schemas from microservices ([7aad91c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7aad91c39c9e78ee3f4c3fb16a702482d23689cf))
* add namespace-specific pod ep ([7cb5033](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7cb5033aaf5c3a4a3efb3479181e89282c5f64f6))
* add projects hub endpoints ([d6d5204](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d6d5204facaf3f03ad6f07427d157454b9ecd7aa))
* **api:** add ability to change root path through env build_image ([aead114](https://github.com/PrivateAIM/node-hub-api-adapter/commit/aead114a408db87437573443aa9c7276d6647889))
* **api:** add dynamic paths to docs build_image ([f2f09fc](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f2f09fc99793a43c777e9e3b7f8792c573ffa903))
* **api:** increase timeout of forwarded requests to 60s build_image ([c99da64](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c99da64d5c3f88cc1061c19e30e28aed788a6880))
* **auth:** add check for robot UUID and send error if robot name used ([f39220f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f39220f1e4a20a0ce10f5d40ad847b0a7e9b6072))
* **auth:** add defensive code for missing token build_image ([aee09a3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/aee09a3b9c37e9ecf810403436975697e34054a3))
* **auth:** add extra auth endpoints and refactor into own router ([edc8ef8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/edc8ef82d39c6b3e343a08b0515d36ed29f2c279))
* **auth:** add token to API GUI ([5e963f8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5e963f87fa416a914b4f9044d37a764c01e3f329))
* **auth:** add token verification and remove secrets ([a0214d6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a0214d64e72a0b5994a5efb0937e1eb1757d9884))
* basic keycloak auth working on test eps ([5ccbc52](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5ccbc520828a5ebce01036012bda42d66b8921ac))
* **cache:** have cache dir created for storing cached information ([4da9e3e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4da9e3e735eb517009c011564a8cc52f4b729686))
* **cli:** enable reload on uvicorn build_image ([35fae65](https://github.com/PrivateAIM/node-hub-api-adapter/commit/35fae6511f09982895e971dae7f373714bda854a))
* **core:** add ability to have different endpoint path compared to downstream service ([1b5072a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1b5072acb0d19cae1ed4db4d0e0466b18c4b3281))
* **core:** improved error catching and logging of errors ([9bba55e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9bba55ec9034d4d870c3cda91eaf371880b167f5))
* enable form data forwarding with put and post methods ([ac241e0](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ac241e09f124ba710d4f87ade1370116542c48cd))
* **error:** include service error in 503 response ([9be663b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9be663b40c922ea4ecb69cc80928609d9d7674a8))
* **filter:** allow Hub endpoints to send any query params for GET requests ([d38394f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d38394f05622b004f718b2b310a55ceb1cb6cfde))
* **filter:** begin allowing all query params for hub GET eps ([bfe793d](https://github.com/PrivateAIM/node-hub-api-adapter/commit/bfe793d75cf10bd3fdd29a6bcccd1b22ebe7f455))
* **filter:** working node ID retrieval and implementation ([6a8b3e1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6a8b3e13c79ddc1318c04966839f986cd805f63b))
* **health:** add downstream service health check ([df15180](https://github.com/PrivateAIM/node-hub-api-adapter/commit/df15180aeb9d9d44839ec539c1391a8e42861ac6))
* **helm:** add random secret generation ([4fb6a3b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4fb6a3bdc310ed360c62468bab076e3637988916))
* **helm:** update helm chart to match node-deployment ([8f7e566](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8f7e5660c270cac5bf821541c3e7e1b65d57ee51))
* **hub:** add /analyses hub endpoint ([1eb80c8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1eb80c8de28e8fadaa31b1fa6f6c8f7554f5565b))
* **hub:** add bucket/files endpoints and models build_image ([8571590](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8571590c57c57957d0fe03b60a7f32b0009df12e))
* **hub:** add debug mode to get all analyses ([04fc302](https://github.com/PrivateAIM/node-hub-api-adapter/commit/04fc302728577efcb60a0ec004daff99e2b96431))
* **hub:** add EPs for gathering containers and images using dummy data ([161dc71](https://github.com/PrivateAIM/node-hub-api-adapter/commit/161dc71f85b44fa3f45c48d35fa7c5a6e2b7692c))
* **hub:** add extra analysis control endpoint for hub build_image ([32aa888](https://github.com/PrivateAIM/node-hub-api-adapter/commit/32aa8887a64bc289444a5a5bf2ec29a9af770236))
* **hub:** add forced hub realm ID filtering ([314a053](https://github.com/PrivateAIM/node-hub-api-adapter/commit/314a053ab4a668dfc2130b138b041ccafc8fd844))
* **hub:** add metadata object class definition ([54fa44f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/54fa44fbe006e436c850ee9b2e75b49dfeb28b33))
* **hub:** add middleware for adding hub token to hub requests ([4b5901b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4b5901b84f4972ded136e52f23b38753e41fca64))
* **hub:** add pp and create containers EP ([3f150dd](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3f150dda4e3941c5c1e0bb9012f24f5b7cbdef43))
* **hub:** begin adding methods for compiling analysis image URL ([b74db09](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b74db09d0c42a49df0e75ce74814b85b8f0dfae0))
* **hub:** first version retrieving node ID using robot username ([2e0240a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2e0240aaef2ebde3e190c3f5434128f6c640d356))
* **hub:** switch to using robot account for hub auth build_image ([8269126](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8269126d8eb1d35c70f0566da5a8ee2dab2e95be))
* **hub:** update image URL retrieval to only include host name for registry_url build_image ([8bc7c47](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8bc7c4715186a4c711485abcb76bf1aafe0cfbd7))
* **hub:** working analysis image URL endpoint ([f034428](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f0344288b92c3156faca0c184837e34561567397))
* **hub:** working projects EP ([b7ebd4b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b7ebd4bab1c862bc4aa0e633b9763f35dbfdfe7b))
* improve hub response models and add analysis EP ([1e63c15](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1e63c15b06c0c258797659723acbee6b544bb461))
* **k8s:** add manifests ([dae1808](https://github.com/PrivateAIM/node-hub-api-adapter/commit/dae1808e9dc182af6b7da8f395e2e69ed7f480b2))
* **kong:** add detailed data store description to project/route list ([6a5f5d6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6a5f5d612525a6485ab70cb4d36ceefcae7f3a5a))
* **kong:** add kong endpoints ([c18d156](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c18d156be02deabee5f6ed00351472b4c5c9aa2c))
* **kong:** add list analyses to kong EPs build_image ([715564a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/715564a61da2156c33622763c9576e334be2786a))
* **kong:** add projects to data store list ([b19ef64](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b19ef64cbdabf21cf5e2d6d25cb7d38f2cf58af0))
* **kong:** add tags to data store "services" in kong build_image ([6837a3c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6837a3ca34b1fbd4a97d18944ebae57284b6d1cb))
* **kong:** combine datastore and project creation in single endpoint ([ebc90c9](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ebc90c9035edb21291d06b4ce5a5ad7806c405b9))
* **kong:** data store deletion now deletes associated projects and analyses ([1b459f7](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1b459f7ef9130759f87a84973ccc94cadb10f7f3))
* **kong:** data store deletion now deletes associated projects and analyses ([c439513](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c439513a72a8f8f1e57ab4bd90eeba1b9b7177fa))
* **logging:** add logging file build_image ([1d77745](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1d7774562baa2ab33c64dbbe2f1f5fcb32941b2b))
* **metadata:** begin adding EPs for frontend metadata collection ([5c2674f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5c2674fa8e0450b6d2d8cb9a06058d0e935e8d41))
* **metadata:** begin adding EPs for frontend metadata collection ([4abc611](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4abc6112cdad9633a14a26e621478260c0638721))
* **models:** add missing or modified response models ([088b546](https://github.com/PrivateAIM/node-hub-api-adapter/commit/088b546646c8cc5c8956b0fde14b151857666ae6))
* **node:** allow multiple node IDs to be stored in cache file ([9a0b024](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9a0b024b35eab82052fe7018260f282ac8757dd3))
* **nodeId:** save node ID as pickle instead of in env vars ([8d410cf](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8d410cf6dae49efca74f3bdefaf9aa28f2f12414))
* **po:** add image parsing step to podorc analysis creation endpoint build_image ([22de1ac](https://github.com/PrivateAIM/node-hub-api-adapter/commit/22de1aca5898a72046c9cc2cc730d8042bec6e27))
* **po:** add log history endpoint build_image ([9aa03b8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9aa03b8615157b43fde9dc77a840023efd20cdee))
* **po:** add response models build_image ([d307f94](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d307f94628db5a1a90b15645659628403cbc3c47))
* **podorc:** add po eps and refactor k8s to podorc build_image ([3279e73](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3279e7304a205ba509f5bff31f1f69c0c2b78fd5))
* **po:** image forward progress build_image ([6021abc](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6021abc1789c3adf0ac101cdbc4664a54ba0e1bb))
* **po:** restrict path variable to UUIDs ([62c50bd](https://github.com/PrivateAIM/node-hub-api-adapter/commit/62c50bd4ae6568f5259bb6d686e9d68ed44e68a7))
* remove schema merging and implement request forwarding ([e8b86d8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e8b86d8977270433879c98480ddb14ebc103336d))
* **results:** update EPs to match results service update build_image ([686e92a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/686e92ac0f1998574945f0235c2abfa7d69f2533))
* **server:** add token endpoint ([e3896c3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e3896c320c62cc3c5373e4d40a4986f4c2a28f45))
* **ui:** add endpoints to gather and spoof data for UI to start properly ([3fae44e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3fae44e2bbadabbd02d4e55f7f9df7999d67bd8d))
* working k8s API example endpoint ([846588a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/846588a6700322384281f7fc5ad9c9266ce48363))
* working read_from_scratch ([8eace59](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8eace5911eaff7ea991f95720a4a772f533d258e))


### Bug Fixes

* add permission to release please ([f2747d1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f2747d1d721b423d526966d9ffe86ab2ca78c403))
* **auth:** add another catch for hub call build_image ([44ace31](https://github.com/PrivateAIM/node-hub-api-adapter/commit/44ace3102d3fbcd0318fc7c8f1c13fddb53a50e8))
* **auth:** missing slash in URL build_image ([e7b1671](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e7b1671b8a156b545a9c7acea46c8910c543f538))
* **auth:** remove urljoin() from IDP URL generation for k8s build_image ([bf52872](https://github.com/PrivateAIM/node-hub-api-adapter/commit/bf52872bdaba4f3d5444b08b759d1210d2791285))
* **ci:** attempted fix to github actions build_image ([3df7ca5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3df7ca51b73bdf304a9065d7a542670a97c59362))
* **core:** handle missing tags ([3e8d0c9](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3e8d0c9f36ad41351de12c79656f34323d8fce90))
* deactivate ([e3d7940](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e3d7940fdec5f808359b54a82294573bf737926d))
* **env:** conf now grabs HUB_REALM_UUID properly ([145021f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/145021f96f353b903c206dc5470f1937d10a2fcb))
* **exceptions:** fix jose exception imports ([9fc8df7](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9fc8df7e3cb0781d0444e7b9e781ff85522cbc69))
* **filter:** set filter by node ID if provided in env build_image ([e395f4f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e395f4fbd09eca53ef20cb403c9a1b2a383f0d8b))
* **form:** serialize form params ([178800a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/178800ab078d3cb99a4852ad74f23b886dd25236))
* **health:** allow string status code for downstream health check build_image ([9c99245](https://github.com/PrivateAIM/node-hub-api-adapter/commit/9c99245dec97da5c68f70483ffac55ce4b76f911))
* **health:** handle failed downstream health checks build_image ([f4c971a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f4c971a371dd9a632154f05db63e8a7ef109ed9b))
* **health:** set correct eps for downstream health checks ([23e0d53](https://github.com/PrivateAIM/node-hub-api-adapter/commit/23e0d53362b17e5f67dcc66c988ac5b796d6bac7))
* **helm:** add initial helm chart ([e0066a1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e0066a1d1731b3aceb4f90fd9ada6837bf546013))
* **helm:** delay livenessProbe in helm ([6e85791](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6e85791665ba2c10344461f56aaddc6901a54b8f))
* **hub:** add check for hub credentials build_image ([d0a704e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d0a704e19a57e8828b799a8e63954333c8bb58b9))
* **hub:** add filter all query params to bucket endpoint ([f59474e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f59474e806c45ddedc7af4a638c74112e868ff72))
* **hub:** add include param to list proposals ([28fa0f1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/28fa0f1adc9a355ed88c53ffa90746db61719405))
* **hub:** add missing optionals build_image ([8614a05](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8614a051bfca56802ef3db7da1edac46a3f89d4b))
* **hub:** add missing query param to decorator ([ceecfd6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/ceecfd6631a51d2b07384bd9c9999c0c44e11c39))
* **hub:** add timeout catch for unreacheable hub ([d6f7871](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d6f7871d99120c04fb1519524627abd1d895b4b0))
* **hub:** fix and improve analysis image url retrieval build_image ([5d04813](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5d0481355e86a59bff2b750df18bc0d74edd2d4c))
* **hub:** make all response fields optional for field filtering build_image ([d6a7394](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d6a7394a9a611925fd2fa77f047860421cc0c852))
* **hub:** properly extract credentials for image build_image ([f5e8a1b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f5e8a1b60e7029d1ee24d2a746b8f3b3a2bde61c))
* **hub:** remove result_status from analyses response model ([a4f5d86](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a4f5d8650165fbf18917dfea079c4adabef27d66))
* **hub:** remove trailing slash in host name for registry_url build_image ([8470e4e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8470e4ecfa214f1d1d969fb2b91996bf3bb5082b))
* **hub:** return proper error message when hub token retrieval fails ([c48825f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c48825f1c177202c5dd507491f4fb4885f9c8f8d))
* **hub:** set approve reject body ([adfb9e8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/adfb9e812b563876025b5422a2b842d9f720a3cb))
* **hub:** set approve reject body to form data ([e58fe4d](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e58fe4d35bef072942230b42084aff1ee1e2b146))
* **hub:** update models to make user_id optional ([7e407a8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7e407a82e55623fe698efda11ed6ea9e958b73d9))
* **hub:** update response models and remove redundant token for tests ([5da04c3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5da04c3962dd8abc43595352d915f27e8ac1bd5f))
* improper package imports ([6b4e1c5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6b4e1c581e92ff8dfe6d0b1dce24b500f3f6bd96))
* **k8s:** fix probe name ([19ca7c4](https://github.com/PrivateAIM/node-hub-api-adapter/commit/19ca7c421a9be0a0c9df4a3f41561b9d03cfcf15))
* **kong:** add missing env variable for kong url build_image ([f4e35a6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f4e35a6e953642d130cacca184c2de63d9ae336f))
* **kong:** change consumer creation to non-uuid username to allow future lookup ([d157209](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d157209d4901c6b22ddf5437d5a1057ad1b1733f))
* **kong:** change response model for to service list build_image ([a53c628](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a53c6282272948865b2a8f4a7762e112c647008d))
* **kong:** clarify project ID required for kong eps ([f2af77f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/f2af77fd2cfe5b9bd3525a193aea383d3e97bfda))
* **kong:** clarify project ID required for kong eps ([b615a41](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b615a41833ae66ae0ebc449b1828e2b660c3123c))
* **kong:** have data store list EP properly return all projects as routes build_image ([242b2a3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/242b2a3feb500b1c1871bbd5792a97deb2deb6c3))
* **kong:** proper project existence check during analysis creation build_image ([7b5f10c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7b5f10c7825da040d19b7356ecd5f1ec50db7edb))
* **kong:** properly pass project ID as string to driver ([2bb7cc6](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2bb7cc6d3029c72a504f7f1b8d003514a313580a))
* **kong:** return proper status code on error build_image ([2becc0a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2becc0a8bbda24ab2600766eea7f2fdd8b205613))
* **kong:** set default routes param in Service to empty rather than null ([7068f41](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7068f41997d70cd3a368a6fd26d3ec071240d91c))
* **kong:** split project get into two different EPs build_image ([16a91b5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/16a91b56e270afab96f426995a31c44e614abfc0))
* **kong:** update plugins for routes to have unique names for instances and avoid conflict ([c6fe7d3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c6fe7d3e6b4d93cb6332f97554401abab95dd88d))
* **logging:** properly set logging after breaking from refactoring ([54958d5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/54958d55f2c8c60a5e213a8e766224956a2eeb11))
* **log:** set stream logging to debug ([699ba08](https://github.com/PrivateAIM/node-hub-api-adapter/commit/699ba08d13e7d30f7d50d1be7e5fcd1d91c89851))
* **logs:** improve logging ([a7f3f5c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a7f3f5cd37fbdc10325e412129967136ecf9c6ae))
* **meta:** add missing meta param to the GET hub response models ([1ac2b7b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1ac2b7b787b60578b775db7149e4ef45be525f35))
* **models:** small fixes to response models build_image ([8463bd0](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8463bd05759a00ee79b9dbeaf74d7284199ca15e))
* override inherited aiohttp method for form data ([31831e9](https://github.com/PrivateAIM/node-hub-api-adapter/commit/31831e968196f6d50a45c7929ef620e551dc0715))
* **p0o:** fix image data gateway for PO by adding a preprocessing routine build_image ([71473a5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/71473a52a4976d0c783a1ab0ffd14cbce543f3f8))
* **po:** add missing option for pod creation build_image ([5427621](https://github.com/PrivateAIM/node-hub-api-adapter/commit/5427621efe8fa25a8f6e83f01e4a506c0db30502))
* **po:** add po prefix to podorc endpoints build_image ([c9bf789](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c9bf789e3497e02d2d2a262924022761c1d8d6e1))
* **po:** bad bruce build_image ([c2789a3](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c2789a339cef05294e1fc2e26c1a056af180405b))
* **podorc:** remove response_class due to errors ([2d89f9b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2d89f9b1d02fe0f6f075d3e392bc927d57fdcb82))
* **pre-commit:** fix exclusion for helm in pre-commit ([acce37c](https://github.com/PrivateAIM/node-hub-api-adapter/commit/acce37c90e2b99999040df572ee9ce7db7b7d518))
* prevent improper env settings import ([700f9b2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/700f9b2f9ccb462a7c3b743e57660b9f3e750011))
* **realm:** make passing hub REALM ID optional ([a1e487e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a1e487e30f37e43b66895172561a609f74e2adc0))
* **results:** fix status code build_image ([19e4816](https://github.com/PrivateAIM/node-hub-api-adapter/commit/19e48161d27c29c6633ef7f8af4719dabf2dc99f))
* **results:** handle response streams properly ([531e94a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/531e94a71f0cd6a1c04efc8bf39266b8dbc7b05b))
* **results:** post & put methods sending malformed content metadata ([e1487eb](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e1487eb6269535b027cd391b68fb47e977c80f82))
* **results:** reenable uploading using results service ([e47c014](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e47c0147ca1fc9e6018a6c9036bd156fda4e0d03))
* **results:** remove response model req from final result ep build_image ([244b5f5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/244b5f559cc1eba4a4aad1594e7f38f8bd11b580))
* set default results service url ([7ea7dd1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7ea7dd13e0c1b52748b7d480d85cfe297158035d))
* string representations of paths and urls ([92259d0](https://github.com/PrivateAIM/node-hub-api-adapter/commit/92259d006c7e963cc821998ed75db7c585354cd0))
* test fix ([1f59fcd](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1f59fcd02e087eb44a337676e025507e6053b3e6))
* test fix ([d227914](https://github.com/PrivateAIM/node-hub-api-adapter/commit/d22791490d2f26f880b319fb53fecd6f328f5039))
* url construction ([650ca16](https://github.com/PrivateAIM/node-hub-api-adapter/commit/650ca16019d76af18ef88ecbf363db4225013f59))


### Performance Improvements

* **auth:** add basic keycloak auth for easier integration and debugging build_image ([e111af4](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e111af42c589a7271ee62af2806d65ef076c18c8))
* **auth:** remove urljoin to prevent non-http URI errors ([37fa44e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/37fa44e35c6831e843a42d1baf1662078add1da7))
* **kong:** improve analysis retrieval from kong ([28746b8](https://github.com/PrivateAIM/node-hub-api-adapter/commit/28746b8877f31cc1a70714292ff44cd1b42465cf))


### Reverts

* **auth:** add api client secret back to settings ([2a2dd83](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2a2dd83fffc303e097aaba236325c06ceea0f233))
* **auth:** remove debug build_image ([a223e19](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a223e1961d56238679ffee00ce1a5a8990ffcfe0))
* **auth:** restore urljoin build_image ([18eb0ca](https://github.com/PrivateAIM/node-hub-api-adapter/commit/18eb0caaccc4932a13b3512da3293e92f2435fea))
* **core:** remove path modification feature ([8dca6af](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8dca6af296b93d5b242d386c84da1b8e4d8cf07d))
* **github:** remove workflow_dispatch ([8998c4b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8998c4bbf43b451a709ded2090d6acff101061f5))
* **hub:** re-enable dependencies for hub ([a1faf8d](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a1faf8dcbaa8b7ec747904e0071f26a0ba91a21c))
* **hub:** re-enable security ([1692028](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1692028a13c680a3bd343c32f4b8b72faa9218e8))
* **kong:** default routes param ([2428c50](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2428c5075b6abecdeb440837c7c89ff4e49b3692))
* **kong:** reenable security ([2509518](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2509518b6c70fe32022bf25d800d2751b6fc6a44))
* **kong:** remove dummy ep build_image ([98c3c75](https://github.com/PrivateAIM/node-hub-api-adapter/commit/98c3c7573f6bdc58901ba801e4b0b98647e3fb52))
* **lint:** revert pre-commit ([4ead397](https://github.com/PrivateAIM/node-hub-api-adapter/commit/4ead3978bba136fe720e06793045a4e0edb4300f))


### Documentation

* add info about env to README ([e0e523e](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e0e523e30599a79521f5767cd1b643e2ef81c755))
* Add notes to README ([7fee384](https://github.com/PrivateAIM/node-hub-api-adapter/commit/7fee384d167593ba4f41f2ce9d17d87406fd97ff))
* add TODO for k8s method ([395f3ef](https://github.com/PrivateAIM/node-hub-api-adapter/commit/395f3eff2d52a69060cb2758ebdd0c67834fa096))
* **api:** update API description ([682090d](https://github.com/PrivateAIM/node-hub-api-adapter/commit/682090dfbe1288dea6c0c5273d268c2dcaadee2d))
* **auth:** add docstring to token ep build_image ([80228c1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/80228c17b6164d551f12d56e839b926d0d549842))
* **auth:** update hub credentials error msg build_image ([882d7c1](https://github.com/PrivateAIM/node-hub-api-adapter/commit/882d7c1b09d5181a5cd7029db1759c80d9bf23dc))
* **conf:** update missing conf variable error message ([457ec53](https://github.com/PrivateAIM/node-hub-api-adapter/commit/457ec53555e71824e7c1038f70775638be1c9fcd))
* **core:** remove unused param from docstring ([cb0794a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/cb0794a1cf7a638a4bc862d39a48da2b1df19251))
* **env:** update README for newly needed env variable ([0dcba37](https://github.com/PrivateAIM/node-hub-api-adapter/commit/0dcba3762d5bb6f113d6a369518498280b88c443))
* **env:** update README for newly needed env variable ([99f062b](https://github.com/PrivateAIM/node-hub-api-adapter/commit/99f062b6210adeace58ed506a691867c6094d921))
* fix README typos build_image ([04c7785](https://github.com/PrivateAIM/node-hub-api-adapter/commit/04c778545ab7a6b286401343d7a6d428e6413df0))
* **helm:** update chart name ([98f5c51](https://github.com/PrivateAIM/node-hub-api-adapter/commit/98f5c5104671fd05837e1770bb05d9fa9c99e521))
* **hub:** fix comments ([e4256ef](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e4256ef40448c6516da7a1affc07f66578c02b62))
* **hub:** update README for needed hub variables ([c439f3f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/c439f3fee04dac0fadd0aadaf2e17f87a04a847e))
* **k8s:** add README for k8s folder build_image ([e1c96ea](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e1c96ea61f4647115d4612ed9b7a90d510dfc74f))
* **kong:** improve datastore example in swagger ([8becce7](https://github.com/PrivateAIM/node-hub-api-adapter/commit/8becce7f4750ba912c2076a3bb10df19ea94572a))
* **logs:** improve logging for requests and errors build_image ([e1cb576](https://github.com/PrivateAIM/node-hub-api-adapter/commit/e1cb5760b649ed99a8113d5f1224173d8b748124))
* **po:** fix po endpoint docstring ([2c8b554](https://github.com/PrivateAIM/node-hub-api-adapter/commit/2c8b554b0858532a4abe410b7a8f28b5476d1e8e))
* **README:** add missing env variable to README build_image ([596e4b7](https://github.com/PrivateAIM/node-hub-api-adapter/commit/596e4b7fb6f1666f8ad3985d612007bd742526ae))
* **README:** remove unused env var from README ([3593704](https://github.com/PrivateAIM/node-hub-api-adapter/commit/3593704315bb00faa9f5a266cfb0c42ebea6c1b1))
* remove unused env variable from README build_image ([b7b387a](https://github.com/PrivateAIM/node-hub-api-adapter/commit/b7b387a26ea8f6d07a03d0a1ca3dee7e7578fc3a))
* remove unused env variables from README ([3165087](https://github.com/PrivateAIM/node-hub-api-adapter/commit/316508780fe63ef51c3be5e02c798ee79afe8202))
* **test:** add some documentation explaining unit tests ([6632547](https://github.com/PrivateAIM/node-hub-api-adapter/commit/6632547e1b694f2b430cba978eb4baa802e8794a))
* **typehint:** add missing class typehints ([1940d78](https://github.com/PrivateAIM/node-hub-api-adapter/commit/1940d785d00bb9aa9b67109813a3f90264b23268))
* update main decorator docstring ([0a536f2](https://github.com/PrivateAIM/node-hub-api-adapter/commit/0a536f298ee320792289d2d34a85ea6c21c7e9b2))
* update README ([0b2e1a5](https://github.com/PrivateAIM/node-hub-api-adapter/commit/0b2e1a58dab67e16609e77ab4675eb23d6b84a70))
* update REAMDE with env variables build_image ([a813b3f](https://github.com/PrivateAIM/node-hub-api-adapter/commit/a813b3fe897a44d1b6eb91c6601ed1fc0ffaa897))
* update template information ([84a06df](https://github.com/PrivateAIM/node-hub-api-adapter/commit/84a06df27c3e901c7e31a219776f80790bc14ca6))
