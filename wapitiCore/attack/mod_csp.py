import re

from wapitiCore.attack.attack import Attack
from wapitiCore.net.web import Request
from wapitiCore.language.vulnerability import Additional, _


CHECK_LISTS = {
    # As default-src is the fallback directive we may want to avoid those duplicates in the future
    "default-src": ["unsafe-inline", "data:", "http:", "https:", "*", "unsafe-eval"],
    "script-src": ["unsafe-inline", "data:", "http:", "https:", "*", "unsafe-eval"],
    "object-src": ["none"],
    "base-uri": ["none", "self"]
}


# This module check the basics recommendations of CSP
class mod_csp(Attack):
    name = "csp"

    @staticmethod
    def csp_header_to_dict(header):
        csp_dict = {}
        regex = re.compile(r"\s*((?:'[^']*')|(?:[^'\s]+))\s*")

        for policy_string in header.split(";"):
            try:
                policy_name, policy_values = policy_string.strip().split(" ", 1)
            except ValueError:
                # Either it is malformed or we reach the end
                continue
            csp_dict[policy_name] = [value.strip("'") for value in regex.findall(policy_values)]

        return csp_dict

    @staticmethod
    def check_policy_values(policy_name, csp_dict):
        """
        This function return the status of the tested element in the CSP as an int. Possible values:
        -1 : the element is missing in the CSP
        0  : the element is set, but his value is not secure
        1  : the element is set and his value is secure
        """

        if policy_name not in csp_dict and "default-src" not in csp_dict:
            return -1

        # The HTTP CSP "default-src" directive serves as a fallback for the other CSP fetch directives.
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/default-src
        policy_values = csp_dict.get(policy_name) or csp_dict["default-src"]

        # If the tested element is default-src or script-src, we must ensure that none of this unsafe values are present
        if policy_name in ["default-src", "script-src"]:
            if any(unsafe_value in policy_values for unsafe_value in CHECK_LISTS[policy_name]):
                return 0
        # If the tested element is none of the previous list, we must ensure that one of this safe values is present
        else:
            if any(safe_value in policy_values for safe_value in CHECK_LISTS[policy_name]):
                return 1
            else:
                return 0

        return 1

    def attack(self):
        url = self.persister.get_root_url()
        request = Request(url)
        response = self.crawler.get(request, follow_redirects=True)

        if "Content-Security-Policy" not in response.headers:
            self.log_red(Additional.MSG_NO_CSP)
            self.add_addition(
                category=Additional.INFO_CSP,
                level=Additional.LOW_LEVEL,
                request=request,
                info=Additional.MSG_NO_CSP
            )
        else:
            csp_dict = self.csp_header_to_dict(response.headers["Content-Security-Policy"])

            for policy_name in CHECK_LISTS:
                result = self.check_policy_values(policy_name, csp_dict)

                if result == -1:
                    self.log_red(Additional.MSG_CSP_MISSING.format(policy_name))
                    self.add_addition(
                        category=Additional.INFO_CSP,
                        level=Additional.LOW_LEVEL,
                        request=request,
                        info=Additional.MSG_CSP_MISSING.format(policy_name)
                    )
                elif result == 0:
                    self.log_red(Additional.MSG_CSP_UNSAFE.format(policy_name))
                    self.add_addition(
                        category=Additional.INFO_CSP,
                        level=Additional.LOW_LEVEL,
                        request=request,
                        info=Additional.MSG_CSP_UNSAFE.format(policy_name)
                    )

        yield
