class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        if len(s) <= 1:
            return len(s)
        
        l = 0
        d = {}
        res = 0
        for r, val in enumerate(s):

            if val in d and d[val] >= l:
                l = d[val] + 1

            d[val] = r

            res = max(res, r - l + 1)
        return res

# s="abcabcbb"
# s="pwwkew"
s="dvdf"

get = Solution()
print(get.lengthOfLongestSubstring(s=s))
