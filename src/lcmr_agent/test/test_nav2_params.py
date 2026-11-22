from lcmr_agent.nav2_params import merge


def test_a_change_replaces_one_nested_value_and_leaves_its_neighbours():
    stock = {"controller_server": {"ros__parameters": {
        "controller_frequency": 10.0,
        "FollowPath": {"sim_time": 1.5, "max_vel_x": 0.22}}}}
    changes = {"controller_server": {"ros__parameters": {"FollowPath": {"sim_time": 2.0}}}}

    merged = merge(stock, changes)

    assert merged == {"controller_server": {"ros__parameters": {
        "controller_frequency": 10.0,
        "FollowPath": {"sim_time": 2.0, "max_vel_x": 0.22}}}}


def test_a_list_value_is_replaced_whole_not_combined():
    stock = {"FollowPath": {"critics": ["RotateToGoal", "Oscillation", "BaseObstacle"]}}

    merged = merge(stock, {"FollowPath": {"critics": ["RotateToGoal", "BaseObstacle"]}})

    assert merged["FollowPath"]["critics"] == ["RotateToGoal", "BaseObstacle"]


def test_no_changes_leaves_the_stock_parameters_as_they_were():
    stock = {"amcl": {"ros__parameters": {"max_particles": 2000}}}

    assert merge(stock, {}) == {"amcl": {"ros__parameters": {"max_particles": 2000}}}


def test_a_new_key_is_added():
    merged = merge({"FollowPath": {"sim_time": 1.5}}, {"FollowPath": {"Oscillation.oscillation_reset_time": 2.0}})

    assert merged == {"FollowPath": {"sim_time": 1.5, "Oscillation.oscillation_reset_time": 2.0}}
