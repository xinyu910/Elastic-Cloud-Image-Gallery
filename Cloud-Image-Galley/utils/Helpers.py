import hashlib
import threading


def MD5Hasher(key, memcacheIP_List):
    """Tool for checking what IP to call for each memcache API calls

    Input:
        key (string): filename


    Returns:
        string: IP to the correct memcache according to the key given.
        list of strings: backup IP list in case the first IP does not work.
    """
    print(key)
    KeyEncode = hashlib.md5(key.encode())
    EncodedhexString = KeyEncode.hexdigest()
    DecimalNumber = int(EncodedhexString, base=16)
    print('dec number', DecimalNumber)
    print('memcahce IP', memcacheIP_List)
    rem1 = DecimalNumber % 16

    # Need to be atomic, cannot let memcacheIP_List change within here
    locker = threading.Lock()
    locker.acquire()
    rem2 = 0

    if len(memcacheIP_List) != 0:
        rem2 = rem1 % len(memcacheIP_List)
        print("rem2", rem2)
    else:
        # No IP available in IP List...
        locker.release()

        return "", []

    IPReturn = memcacheIP_List[rem2]
    ListBackUp = (memcacheIP_List.copy())
    locker.release()
    print(IPReturn)
    return IPReturn, ListBackUp
