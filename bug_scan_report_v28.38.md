# ZRONG v28.38 Bug Scan Report

## Scan Date: 2026-04-27
## Scope: Full codebase - crawler.py, utils.py, parsers/, sources/, config files

---

## 🔴 CRITICAL BUGS (Must Fix)

### 1. crawler.py:145-147 - `bool` shadowing built-in
**Line 145-147**: `bool` is used as a variable name in list comprehensions, shadowing Python built-in.
```python
bool = [True, False]  # This shadows built-in bool()
```
**Impact**: Could cause subtle bugs if `bool()` is called later in the same scope.
**Fix**: Rename variable to `bool_values` or `flags`.

### 2. crawler.py:1282 - Undefined variable `v`
**Line 1282**: Variable `v` referenced but not defined in scope.
```python
# In some error handling path, v is used without definition
```
**Fix**: Define `v` or use correct variable name.

### 3. crawler.py:1494-1495 - Undefined variable `region`
**Line 1494-1495**: `region` variable used before assignment in `get_region()` fallback.
**Fix**: Ensure `region` is always defined before use.

### 4. crawler.py:1800 - Undefined variable `h`
**Line 1800**: `h` used in node deduplication but not defined.
**Fix**: Use correct hash variable.

### 5. crawler.py:240 - Undefined variable `v`
**Line 240**: Similar to line 1282, `v` undefined.

### 6. crawler.py:873 - `tls_ok` undefined in exception handler
**Line 873**: `tls_ok` referenced in exception path but defined in try block.
**Fix**: Initialize `tls_ok = False` before try.

### 7. crawler.py:261-263 - `bool` shadowing (same as #1)
**Lines 261-263**: Multiple `bool` variable shadowing.

### 8. crawler.py:273 - Undefined variable `v`
**Line 273**: Another undefined `v`.

### 9. crawler.py:1781 - `local_nodes` undefined
**Line 1781**: `local_nodes` referenced in exception handler.
**Fix**: Initialize before try.

### 10. crawler.py:1863 - `usable` undefined
**Line 1863**: `usable` variable undefined in scope.

### 11. crawler.py:1574 - `bool` shadowing
**Line 1574**: Another `bool` shadowing.

### 12. crawler.py:1782-1783 - `h` and `is_yaml` undefined
**Lines 1782-1783**: Variables used in exception path without initialization.

### 13. crawler.py:1870 - `tls_ok` undefined
**Line 1870**: Same as #6.

### 14. crawler.py:895 - `ConnectionResetError`/`ConnectionAbortedError` in bare except
**Line 895**: These exceptions caught in bare `except:` block - but they're already caught by the specific `except (ConnectionResetError, ConnectionAbortedError)` above.
**Fix**: Remove redundant bare except or make it specific.

### 15. crawler.py:1373 - `out` undefined
**Line 1373**: `out` variable undefined in Clash output parsing.
**Fix**: Initialize `out = ""` before try.

### 16. crawler.py:1777-1779 - Multiple undefineds
**Lines 1777-1779**: `local_nodes`, `h` undefined in exception paths.

### 17. crawler.py:2056, 2074, 2013 - `fl` undefined
**Lines 2056, 2074, 2013**: `fl` (flag) variable undefined in naming code.
**Fix**: Ensure `fl` always has a value.

---

## 🟡 MODERATE BUGS (Should Fix)

### 18. utils.py:55 - `bool` shadowing
**Line 55**: `bool` used as variable name.

### 19. parsers/common.py:33-35, 46, 127-128, 149-151, 161 - Multiple issues
**Lines 33-35**: `bool` shadowing
**Line 46**: `bool` shadowing  
**Lines 127-128**: `k`, `v` undefined in dict comprehension fallback
**Lines 149-151**: `bool` shadowing
**Line 161**: `k` undefined

### 20. parsers/ss.py:24-45 - Variables undefined in exception fallback
**Lines 24-45**: `method_pwd`, `server_info`, `pwd` undefined in fallback path.
**Fix**: Initialize variables before try-except.

### 21. parsers/vless.py:45-46 - `pbk`, `sid` undefined
**Lines 45-46**: Variables used in reality check but may be undefined.

### 22. sources/subscription.py:96,101,123,136,149,178,271,376,387,432,447,483,428 - Multiple undefineds
**Multiple lines**: `bool` shadowing and undefined variables in async functions.

### 23. sources/telegram.py:107,126,237,242,274 - Undefined variables
**Multiple lines**: `bool` shadowing, `before`, `meta` undefined.

---

## 🟢 MINOR ISSUES (Nice to Fix)

### 24. check_proxies.py:19,28,29,48,57 - Undefined variables
**Multiple lines**: Script has undefined variables making it non-functional standalone.

### 25. _upload_zrong.py:48 - Bare except
**Line 48**: `except:` without exception type - catches SystemExit, KeyboardInterrupt.

### 26. gen_cn_cidr.py - No error fallback
**Issue**: If APNIC download fails, script raises exception with no fallback CIDR data.

### 27. sources.yaml - No validation
**Issue**: No schema validation for sources.yaml - malformed config causes silent failures.

### 28. .github/workflows/update.yml - ubuntu-latest not pinned
**Issue**: Using `ubuntu-latest` which may change - should pin to `ubuntu-22.04`.

---

## 📊 Summary

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 Critical | 17 | Undefined variables, built-in shadowing |
| 🟡 Moderate | 6 | Variable scope issues in parsers/sources |
| 🟢 Minor | 5 | Code quality, bare excepts, config issues |
| **Total** | **28** | |

---

## 🔧 Fix Strategy

1. **Phase 1**: Fix all `bool` shadowing (replace with `bool_values`)
2. **Phase 2**: Fix all undefined variables (initialize before use)
3. **Phase 3**: Fix bare excepts (use specific exception types)
4. **Phase 4**: Add defensive checks and fallbacks
5. **Phase 5**: Verify with static analysis
