from glob import glob

from setuptools import find_packages, setup

package_name = "lcmr_agent"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*")),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/maps", glob("maps/*")),
    ],
    install_requires=["setuptools", "pydantic>=2", "pyyaml", "anthropic"],
    zip_safe=True,
    description="LLM agent that directs a mobile robot through six typed navigation tools.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={"console_scripts": ["chat = lcmr_agent.console:main", "replay = lcmr_agent.replay:main",
                                        "map_tour = lcmr_agent.map_tour:main"]},
)
